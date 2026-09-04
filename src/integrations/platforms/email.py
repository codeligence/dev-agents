"""Email platform service for dev-agents-claw.

Receives messages via IMAP polling and replies via SMTP.
Ported from hermes-agent/gateway/platforms/email.py (MIT).

Environment variables:
    EMAIL_ADDRESS       — Email address for the agent
    EMAIL_PASSWORD      — Email password or app-specific password
    EMAIL_IMAP_HOST     — IMAP server host (e.g. imap.gmail.com)
    EMAIL_IMAP_PORT     — IMAP server port (default: 993)
    EMAIL_SMTP_HOST     — SMTP server host (e.g. smtp.gmail.com)
    EMAIL_SMTP_PORT     — SMTP server port (default: 587)
    EMAIL_POLL_INTERVAL — Seconds between mailbox checks (default: 15)
    EMAIL_ALLOWED_USERS — Comma-separated allowed sender addresses (optional)
    EMAIL_VERIFY_DKIM   — Require a valid, aligned DKIM signature (default: true)

Sender authentication:
    A ``From:`` header is trivially forgeable, so on its own
    ``EMAIL_ALLOWED_USERS`` authenticates nothing — anyone can claim to be an
    allowed sender and drive the agent. Incoming mail is therefore DKIM-verified
    and the signing domain must align with the ``From:`` domain before the
    allowlist is consulted. Set ``EMAIL_VERIFY_DKIM=false`` only when something
    upstream (a gateway, a trusted relay) already authenticates senders.
"""

from __future__ import annotations

from datetime import UTC, datetime
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING, Any
import asyncio
import email as email_lib
import imaplib
import os
import re
import smtplib
import ssl
import uuid

from integrations.platforms.base import BasePlatformService, PlatformMessage

if TYPE_CHECKING:
    from collections.abc import Callable

# Automated sender patterns — emails from these are silently ignored
_NOREPLY_PATTERNS = (
    "noreply",
    "no-reply",
    "no_reply",
    "donotreply",
    "do-not-reply",
    "mailer-daemon",
    "postmaster",
    "bounce",
    "notifications@",
    "automated@",
    "auto-confirm",
    "auto-reply",
    "automailer",
)

# RFC headers that indicate bulk/automated mail
_AUTOMATED_HEADERS: dict[str, Callable[[str], bool]] = {
    "Auto-Submitted": lambda v: v.lower() != "no",
    "Precedence": lambda v: v.lower() in ("bulk", "list", "junk"),
    "X-Auto-Response-Suppress": lambda v: bool(v),
    "List-Unsubscribe": lambda v: bool(v),
}

# Gmail-safe max length per email body
MAX_MESSAGE_LENGTH = 50_000


# ---------------------------------------------------------------------------
# DKIM sender authentication
# ---------------------------------------------------------------------------


def _domain_of(address: str) -> str:
    """Return the lower-cased domain part of an email address."""
    return address.rpartition("@")[2].strip().lower()


def _is_aligned(signing_domain: str, from_domain: str) -> bool:
    """Whether a DKIM ``d=`` domain covers *from_domain* (relaxed alignment).

    Exact match, or the From domain is a subdomain of the signing domain.
    Without this check any validly-signed mail would pass — a Gmail-signed
    message claiming ``From: ceo@yourcompany.com`` included.
    """
    if not signing_domain or not from_domain:
        return False
    return from_domain == signing_domain or from_domain.endswith(f".{signing_domain}")


def verify_dkim(raw_email: bytes, sender_addr: str) -> tuple[bool, str]:
    """Verify the DKIM signature on *raw_email* and check domain alignment.

    Returns ``(ok, reason)``; *reason* is empty when verification succeeded.
    Performs blocking DNS lookups, so it must be called from a worker thread.
    """
    import dkim

    try:
        verifier = dkim.DKIM(raw_email)
        if not verifier.verify():
            return False, "DKIM signature failed verification"
    except dkim.DKIMException as exc:
        return False, f"DKIM signature malformed: {exc}"
    except Exception as exc:  # DNS failures, malformed keys, …
        return False, f"DKIM verification error: {exc}"

    signing_domain = (verifier.signature_fields.get(b"d") or b"").decode(
        "utf-8", errors="replace"
    )
    from_domain = _domain_of(sender_addr)
    if not _is_aligned(signing_domain.lower(), from_domain):
        return False, (
            f"DKIM domain {signing_domain!r} does not align with From domain "
            f"{from_domain!r}"
        )
    return True, ""


# ---------------------------------------------------------------------------
# Helpers (ported from hermes-agent)
# ---------------------------------------------------------------------------


def _is_automated_sender(address: str, headers: dict[str, str]) -> bool:
    """Return True if this email is from an automated/noreply source."""
    addr = address.lower()
    if any(pattern in addr for pattern in _NOREPLY_PATTERNS):
        return True
    for header, check in _AUTOMATED_HEADERS.items():
        value = headers.get(header, "")
        if value and check(value):
            return True
    return False


def _decode_header_value(raw: str) -> str:
    """Decode an RFC 2047 encoded email header into a plain string."""
    parts = decode_header(raw)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def _extract_text_body(msg: email_lib.message.Message) -> str:
    """Extract the plain-text body from a potentially multipart email."""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition:
                continue
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    charset = part.get_content_charset() or "utf-8"
                    return payload.decode(charset, errors="replace")
        # Fallback: try text/html and strip tags
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in disposition:
                continue
            if content_type == "text/html":
                payload = part.get_payload(decode=True)
                if isinstance(payload, bytes):
                    charset = part.get_content_charset() or "utf-8"
                    html = payload.decode(charset, errors="replace")
                    return _strip_html(html)
        return ""
    else:
        payload = msg.get_payload(decode=True)
        if isinstance(payload, bytes):
            charset = msg.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace")
            if msg.get_content_type() == "text/html":
                return _strip_html(text)
            return text
        return ""


def _strip_html(html: str) -> str:
    """Naive HTML tag stripper for fallback text extraction."""
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<p[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_email_address(raw: str) -> str:
    """Extract bare email address from 'Name <addr>' format."""
    match = re.search(r"<([^>]+)>", raw)
    if match:
        return match.group(1).strip().lower()
    return raw.strip().lower()


# ---------------------------------------------------------------------------
# EmailService
# ---------------------------------------------------------------------------


class EmailService(BasePlatformService):
    """Email platform service using IMAP (receive) and SMTP (send)."""

    def __init__(self) -> None:
        super().__init__("email")

        self._address = os.getenv("EMAIL_ADDRESS", "")
        self._password = os.getenv("EMAIL_PASSWORD", "")
        self._imap_host = os.getenv("EMAIL_IMAP_HOST", "")
        self._imap_port = int(os.getenv("EMAIL_IMAP_PORT", "993"))
        self._smtp_host = os.getenv("EMAIL_SMTP_HOST", "")
        self._smtp_port = int(os.getenv("EMAIL_SMTP_PORT", "587"))
        self._poll_interval = int(os.getenv("EMAIL_POLL_INTERVAL", "15"))

        self._allowed_users = self.get_authorized_ids("EMAIL_ALLOWED_USERS")

        # Sender authentication. Enabled by default: without it the From
        # header — and therefore EMAIL_ALLOWED_USERS — is forgeable.
        self._verify_dkim = self.env_flag("EMAIL_VERIFY_DKIM", default=True)
        if self._verify_dkim:
            try:
                import dkim  # noqa: F401
            except ImportError as exc:
                raise RuntimeError(
                    "DKIM verification is enabled but 'dkimpy' is not installed. "
                    "Install it with: pip install 'dev-agents[email]' — or set "
                    "EMAIL_VERIFY_DKIM=false if senders are already "
                    "authenticated upstream."
                ) from exc
        else:
            self.logger.warning(
                "DKIM verification is disabled — the From header is forgeable, "
                "so EMAIL_ALLOWED_USERS cannot authenticate senders on its own"
            )

        # UID-based deduplication
        self._seen_uids: set[bytes] = set()
        self._seen_uids_max: int = 2000

        # Thread context: (recipient, incoming Message-ID) -> {subject}
        # Keyed by both so a single sender with multiple concurrent threads
        # does not have later messages overwrite earlier reply headers.
        self._thread_context: dict[tuple[str, str], dict[str, str]] = {}
        self._thread_context_max: int = 2000

    # -- BasePlatformService interface ----------------------------------------

    async def connect(self) -> bool:
        """Test IMAP+SMTP connections, seed seen UIDs, then poll forever."""
        # Test IMAP
        try:
            imap = imaplib.IMAP4_SSL(self._imap_host, self._imap_port, timeout=30)
            imap.login(self._address, self._password)
            imap.select("INBOX")
            # Seed seen UIDs so we only process messages arriving after startup
            status, data = imap.uid("search", "ALL")
            if status == "OK" and data and data[0]:
                for uid in data[0].split():
                    self._seen_uids.add(uid)
            self._trim_seen_uids()
            imap.logout()
            self.logger.info(
                "IMAP connection OK — %d existing messages skipped",
                len(self._seen_uids),
            )
        except Exception as e:
            self.logger.error("IMAP connection failed: %s", e)
            return False

        # Test SMTP
        try:
            smtp = smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=30)
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(self._address, self._password)
            smtp.quit()
            self.logger.info("SMTP connection OK")
        except Exception as e:
            self.logger.error("SMTP connection failed: %s", e)
            return False

        # Enter poll loop (blocks until cancelled)
        await self._poll_loop()
        return True

    async def disconnect(self) -> None:
        pass  # _run_loop handles cancellation

    async def send_response(
        self, chat_id: str, thread_id: str, text: str
    ) -> str | None:
        """Send an email reply to *chat_id* (a sender address).

        Returns the outgoing Message-ID on success, or ``None`` on failure.
        Email does not support edits, so the returned ID is informational
        only — status updates are suppressed by ``PlatformAgentContext``
        via ``supports_updates = False``.
        """
        try:
            loop = asyncio.get_running_loop()
            message_id = await loop.run_in_executor(
                None, self._send_email, chat_id, thread_id, text
            )
            return message_id
        except Exception as e:
            self.logger.error("Send failed to %s: %s", chat_id, e)
            return None

    # -- IMAP polling ---------------------------------------------------------

    async def _poll_loop(self) -> None:
        """Poll IMAP for new messages at regular intervals."""
        while True:
            try:
                await self._check_inbox()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger.error("Poll error: %s", e)
            await asyncio.sleep(self._poll_interval)

    async def _check_inbox(self) -> None:
        """Check INBOX for unseen messages and dispatch them."""
        loop = asyncio.get_running_loop()
        messages = await loop.run_in_executor(None, self._fetch_new_messages)
        for msg_data in messages:
            await self._handle_email(msg_data)

    def _fetch_new_messages(self) -> list[dict[str, Any]]:
        """Fetch new (unseen) messages from IMAP. Runs in executor thread."""
        results: list[dict[str, Any]] = []
        try:
            imap = imaplib.IMAP4_SSL(self._imap_host, self._imap_port, timeout=30)
            try:
                imap.login(self._address, self._password)
                imap.select("INBOX")

                status, data = imap.uid("search", "UNSEEN")
                if status != "OK" or not data or not data[0]:
                    return results

                for uid in data[0].split():
                    if uid in self._seen_uids:
                        continue
                    self._seen_uids.add(uid)
                    if len(self._seen_uids) > self._seen_uids_max:
                        self._trim_seen_uids()

                    status, msg_data = imap.uid("fetch", uid, "(RFC822)")
                    if status != "OK":
                        continue

                    raw_email = msg_data[0][1]
                    msg = email_lib.message_from_bytes(raw_email)

                    sender_raw = msg.get("From", "")
                    sender_addr = _extract_email_address(sender_raw)
                    sender_name = _decode_header_value(sender_raw)
                    if "<" in sender_name:
                        sender_name = sender_name.split("<")[0].strip().strip('"')

                    subject = _decode_header_value(msg.get("Subject", "(no subject)"))
                    message_id = msg.get("Message-ID", "")
                    in_reply_to = msg.get("In-Reply-To", "")

                    msg_headers = dict(msg.items())
                    if _is_automated_sender(sender_addr, msg_headers):
                        self.logger.debug("Skipping automated sender: %s", sender_addr)
                        continue

                    body = _extract_text_body(msg)

                    # Verified here rather than in _handle_email: this runs in
                    # a worker thread and DKIM does blocking DNS lookups.
                    dkim_ok, dkim_reason = (
                        verify_dkim(raw_email, sender_addr)
                        if self._verify_dkim
                        else (True, "")
                    )

                    results.append(
                        {
                            "uid": uid,
                            "sender_addr": sender_addr,
                            "sender_name": sender_name,
                            "subject": subject,
                            "message_id": message_id,
                            "in_reply_to": in_reply_to,
                            "body": body,
                            "date": msg.get("Date", ""),
                            "dkim_ok": dkim_ok,
                            "dkim_reason": dkim_reason,
                        }
                    )
            finally:
                try:
                    imap.logout()
                except Exception as logout_exc:
                    self.logger.debug("IMAP logout failed: %s", logout_exc)
        except Exception as e:
            self.logger.error("IMAP fetch error: %s", e)
        return results

    # -- Message handling -----------------------------------------------------

    async def _handle_email(self, msg_data: dict[str, Any]) -> None:
        """Convert a fetched email into a PlatformMessage and dispatch it."""
        sender_addr = msg_data["sender_addr"]

        # Skip self-messages
        if sender_addr == self._address.lower():
            return

        if _is_automated_sender(sender_addr, {}):
            self.logger.debug("Dropping automated sender at dispatch: %s", sender_addr)
            return

        # Sender authentication precedes authorization: the allowlist below
        # is only meaningful once the From address is known to be genuine.
        if not msg_data.get("dkim_ok", False):
            self.logger.warning(
                "Ignoring email from %s — sender not authenticated (%s)",
                sender_addr,
                msg_data.get("dkim_reason") or "no DKIM signature",
            )
            return

        # Check allowed users
        if self._allowed_users is not None and sender_addr not in self._allowed_users:
            self.logger.info("Ignoring email from unauthorized sender: %s", sender_addr)
            return

        subject = msg_data["subject"]
        body = msg_data["body"].strip()

        # Include subject as context for non-reply emails
        text = body
        if subject and not subject.startswith("Re:"):
            text = f"[Subject: {subject}]\n\n{body}"

        # Store thread context keyed by (sender, incoming Message-ID) so
        # concurrent threads from the same sender stay isolated.
        incoming_msg_id = msg_data["message_id"]
        self._thread_context[(sender_addr, incoming_msg_id)] = {"subject": subject}
        if len(self._thread_context) > self._thread_context_max:
            self._trim_thread_context()

        message = PlatformMessage(
            user_name=msg_data["sender_name"] or sender_addr,
            user_id=sender_addr,
            content=text or "(empty email)",
            date=datetime.now(UTC),
            thread_id=msg_data["message_id"],
            channel_id=sender_addr,
            platform_name="email",
        )

        self.logger.info("New message from %s", sender_addr)
        self.logger.debug("Subject from %s: %s", sender_addr, subject)
        await self._dispatch_message(message)

    # -- SMTP sending ---------------------------------------------------------

    def _send_email(self, to_addr: str, thread_id: str, body: str) -> str:
        """Send an email via SMTP. Runs in executor thread."""
        msg = MIMEMultipart()
        msg["From"] = self._address
        msg["To"] = to_addr

        ctx = self._thread_context.get((to_addr, thread_id), {})
        subject = ctx.get("subject", "Agent Reply")
        if not subject.startswith("Re:"):
            subject = f"Re: {subject}"
        # Sanitize against CRLF header injection (RFC 5322)
        subject = subject.replace("\r", "").replace("\n", " ")
        msg["Subject"] = subject

        # Threading headers: thread_id is the incoming Message-ID we're replying to.
        if thread_id:
            msg["In-Reply-To"] = thread_id
            msg["References"] = thread_id

        domain = self._address.split("@")[1] if "@" in self._address else "localhost"
        msg_id = f"<claw-{uuid.uuid4().hex[:12]}@{domain}>"
        msg["Message-ID"] = msg_id

        # Split long messages
        chunks = self.truncate_message(body, MAX_MESSAGE_LENGTH)
        msg.attach(MIMEText(chunks[0], "plain", "utf-8"))

        smtp = smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=30)
        try:
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(self._address, self._password)
            smtp.send_message(msg)
        finally:
            try:
                smtp.quit()
            except Exception:
                smtp.close()

        self.logger.info("Sent reply to %s", to_addr)
        self.logger.debug("Reply subject to %s: %s", to_addr, subject)

        # Send remaining chunks as follow-up emails (iterative, not recursive)
        for chunk in chunks[1:]:
            try:
                follow_up = MIMEMultipart()
                follow_up["From"] = self._address
                follow_up["To"] = to_addr
                follow_up["Subject"] = subject
                if thread_id:
                    follow_up["In-Reply-To"] = thread_id
                    follow_up["References"] = thread_id
                follow_up["Message-ID"] = f"<claw-{uuid.uuid4().hex[:12]}@{domain}>"
                follow_up.attach(MIMEText(chunk, "plain", "utf-8"))

                smtp2 = smtplib.SMTP(self._smtp_host, self._smtp_port, timeout=30)
                try:
                    smtp2.starttls(context=ssl.create_default_context())
                    smtp2.login(self._address, self._password)
                    smtp2.send_message(follow_up)
                finally:
                    try:
                        smtp2.quit()
                    except Exception:
                        smtp2.close()
            except Exception:
                self.logger.exception("Failed to send follow-up chunk to %s", to_addr)

        return msg_id

    # -- UID housekeeping -----------------------------------------------------

    def _trim_seen_uids(self) -> None:
        """Keep only the most recent UIDs to prevent unbounded memory growth."""
        if len(self._seen_uids) <= self._seen_uids_max:
            return
        try:
            sorted_uids = sorted(self._seen_uids, key=lambda u: int(u))
            keep = self._seen_uids_max // 2
            self._seen_uids = set(sorted_uids[-keep:])
        except (ValueError, TypeError):
            self._seen_uids = set(list(self._seen_uids)[-self._seen_uids_max // 2 :])

    def _trim_thread_context(self) -> None:
        """Drop oldest thread contexts. Relies on dict insertion order."""
        keep = self._thread_context_max // 2
        self._thread_context = dict(list(self._thread_context.items())[-keep:])
