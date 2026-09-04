"""Tests for EmailService — IMAP/SMTP logic without real connections."""

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import AsyncMock, MagicMock, patch
import os

import pytest

from integrations.platforms.email import (
    EmailService,
    _decode_header_value,
    _extract_email_address,
    _extract_text_body,
    _is_aligned,
    _is_automated_sender,
    _strip_html,
    verify_dkim,
)

# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_extract_email_address_angle_brackets(self):
        assert (
            _extract_email_address("Alice <alice@example.com>") == "alice@example.com"
        )

    def test_extract_email_address_bare(self):
        assert _extract_email_address("bob@example.com") == "bob@example.com"

    def test_extract_email_address_uppercase(self):
        assert _extract_email_address("BOB@Example.COM") == "bob@example.com"

    def test_decode_header_plain(self):
        assert _decode_header_value("Hello World") == "Hello World"

    def test_strip_html_basic(self):
        result = _strip_html("<p>Hello</p><br>World")
        assert "Hello" in result
        assert "World" in result
        assert "<p>" not in result

    def test_strip_html_entities(self):
        result = _strip_html("A &amp; B &lt; C &gt; D")
        assert result == "A & B < C > D"

    def test_is_automated_sender_noreply(self):
        assert _is_automated_sender("noreply@example.com", {}) is True
        assert _is_automated_sender("do-not-reply@example.com", {}) is True
        assert _is_automated_sender("alice@example.com", {}) is False

    def test_is_automated_sender_headers(self):
        assert (
            _is_automated_sender("x@x.com", {"Auto-Submitted": "auto-generated"})
            is True
        )
        assert _is_automated_sender("x@x.com", {"Precedence": "bulk"}) is True
        assert _is_automated_sender("x@x.com", {"Auto-Submitted": "no"}) is False

    def test_is_automated_sender_list_unsubscribe(self):
        assert (
            _is_automated_sender(
                "x@x.com", {"List-Unsubscribe": "<mailto:unsub@x.com>"}
            )
            is True
        )


class TestExtractTextBody:
    def test_plain_text(self):
        msg = MIMEText("Hello plain", "plain", "utf-8")
        assert _extract_text_body(msg) == "Hello plain"

    def test_html_fallback(self):
        msg = MIMEText("<p>Hello HTML</p>", "html", "utf-8")
        result = _extract_text_body(msg)
        assert "Hello HTML" in result
        assert "<p>" not in result

    def test_multipart_prefers_plain(self):
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText("<p>HTML</p>", "html", "utf-8"))
        msg.attach(MIMEText("Plain text", "plain", "utf-8"))
        assert _extract_text_body(msg) == "Plain text"

    def test_multipart_html_fallback(self):
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText("<p>Only HTML</p>", "html", "utf-8"))
        result = _extract_text_body(msg)
        assert "Only HTML" in result


# ---------------------------------------------------------------------------
# EmailService tests
# ---------------------------------------------------------------------------


class TestEmailService:
    def _make_service(self, **env_overrides):
        env = {
            "EMAIL_ADDRESS": "bot@example.com",
            "EMAIL_PASSWORD": "secret",
            "EMAIL_IMAP_HOST": "imap.example.com",
            "EMAIL_SMTP_HOST": "smtp.example.com",
            **env_overrides,
        }
        with patch.dict(os.environ, env, clear=False):
            return EmailService()

    def test_init(self):
        svc = self._make_service()
        assert svc.name == "email"
        assert svc._address == "bot@example.com"
        assert svc._imap_port == 993
        assert svc._smtp_port == 587

    def test_allowed_users(self):
        svc = self._make_service(EMAIL_ALLOWED_USERS="a@x.com, b@x.com")
        assert svc._allowed_users == {"a@x.com", "b@x.com"}

    def test_allowed_users_empty(self):
        svc = self._make_service()
        assert svc._allowed_users is None

    def test_trim_seen_uids(self):
        svc = self._make_service()
        svc._seen_uids_max = 10
        svc._seen_uids = {str(i).encode() for i in range(20)}
        svc._trim_seen_uids()
        assert len(svc._seen_uids) <= 10

    @pytest.mark.asyncio
    async def test_thread_context_bounded(self):
        """_thread_context is trimmed when it exceeds its cap, mirroring _seen_uids."""
        svc = self._make_service()
        svc._thread_context_max = 10
        for i in range(25):
            await svc._handle_email(
                {
                    "sender_addr": f"user{i}@example.com",
                    "sender_name": f"User {i}",
                    "subject": f"Subject {i}",
                    "message_id": f"<{i}@x>",
                    "in_reply_to": "",
                    "body": "body",
                    "date": "",
                    "dkim_ok": True,
                }
            )
        assert len(svc._thread_context) <= svc._thread_context_max

    @pytest.mark.asyncio
    async def test_handle_email_skips_self(self):
        svc = self._make_service()
        svc._dispatch_message = AsyncMock()

        msg_data = {
            "sender_addr": "bot@example.com",
            "sender_name": "Bot",
            "subject": "Test",
            "message_id": "<1@x>",
            "in_reply_to": "",
            "body": "Hello",
            "date": "",
            "dkim_ok": True,
        }
        await svc._handle_email(msg_data)
        svc._dispatch_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_email_skips_automated(self):
        svc = self._make_service()
        svc._dispatch_message = AsyncMock()

        msg_data = {
            "sender_addr": "noreply@example.com",
            "sender_name": "No Reply",
            "subject": "Automated",
            "message_id": "<2@x>",
            "in_reply_to": "",
            "body": "Auto",
            "date": "",
            "dkim_ok": True,
        }
        await svc._handle_email(msg_data)
        svc._dispatch_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_email_skips_unauthorized(self):
        svc = self._make_service(EMAIL_ALLOWED_USERS="allowed@x.com")
        svc._dispatch_message = AsyncMock()

        msg_data = {
            "sender_addr": "stranger@x.com",
            "sender_name": "Stranger",
            "subject": "Hi",
            "message_id": "<3@x>",
            "in_reply_to": "",
            "body": "Hello",
            "date": "",
            "dkim_ok": True,
        }
        await svc._handle_email(msg_data)
        svc._dispatch_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_email_dispatches_valid(self):
        svc = self._make_service()
        svc._dispatch_message = AsyncMock()

        msg_data = {
            "sender_addr": "alice@example.com",
            "sender_name": "Alice",
            "subject": "Question",
            "message_id": "<4@x>",
            "in_reply_to": "",
            "body": "What is this repo?",
            "date": "",
            "dkim_ok": True,
        }
        await svc._handle_email(msg_data)
        svc._dispatch_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_email_includes_subject(self):
        svc = self._make_service()
        dispatched = []

        async def _mock_dispatch(message):
            dispatched.append(message)

        svc._dispatch_message = _mock_dispatch

        msg_data = {
            "sender_addr": "alice@example.com",
            "sender_name": "Alice",
            "subject": "Bug Report",
            "message_id": "<5@x>",
            "in_reply_to": "",
            "body": "Found a bug",
            "date": "",
            "dkim_ok": True,
        }
        await svc._handle_email(msg_data)
        assert len(dispatched) == 1
        assert "[Subject: Bug Report]" in dispatched[0].content

    @pytest.mark.asyncio
    async def test_handle_email_skips_subject_on_reply(self):
        svc = self._make_service()
        dispatched = []

        async def _mock_dispatch(message):
            dispatched.append(message)

        svc._dispatch_message = _mock_dispatch

        msg_data = {
            "sender_addr": "alice@example.com",
            "sender_name": "Alice",
            "subject": "Re: Bug Report",
            "message_id": "<6@x>",
            "in_reply_to": "<5@x>",
            "body": "More details",
            "date": "",
            "dkim_ok": True,
        }
        await svc._handle_email(msg_data)
        assert len(dispatched) == 1
        assert "[Subject:" not in dispatched[0].content

    def test_send_email_sanitizes_subject_crlf(self):
        """Subject header must be stripped of CRLF to prevent header injection."""
        svc = self._make_service()
        svc._thread_context[("alice@x.com", "<1@x>")] = {
            "subject": "Normal\r\nBcc: attacker@evil.com"
        }

        with patch("integrations.platforms.email.smtplib") as mock_smtp_mod:
            mock_smtp = MagicMock()
            mock_smtp_mod.SMTP.return_value = mock_smtp

            svc._send_email("alice@x.com", "<1@x>", "Hello")

            sent_msg = mock_smtp.send_message.call_args[0][0]
            subject = sent_msg["Subject"]
            # CRLF stripped — "Bcc:" is now harmless inline text, not a header
            assert "\r" not in subject
            assert "\n" not in subject

    @pytest.mark.asyncio
    async def test_thread_context_isolated_per_thread(self):
        """Two concurrent threads from one sender must not overwrite each other's
        reply headers. Regression for keying _thread_context by sender alone.
        """
        svc = self._make_service()
        svc._dispatch_message = AsyncMock()

        first = {
            "sender_addr": "alice@example.com",
            "sender_name": "Alice",
            "subject": "Thread A",
            "message_id": "<a1@x>",
            "in_reply_to": "",
            "body": "First thread",
            "date": "",
            "dkim_ok": True,
        }
        second = {
            "sender_addr": "alice@example.com",
            "sender_name": "Alice",
            "subject": "Thread B",
            "message_id": "<b1@x>",
            "in_reply_to": "",
            "body": "Second, unrelated thread",
            "date": "",
            "dkim_ok": True,
        }
        await svc._handle_email(first)
        await svc._handle_email(second)

        ctx_a = svc._thread_context[("alice@example.com", "<a1@x>")]
        ctx_b = svc._thread_context[("alice@example.com", "<b1@x>")]
        assert ctx_a["subject"] == "Thread A"
        assert ctx_b["subject"] == "Thread B"


# ---------------------------------------------------------------------------
# Sender authentication (DKIM)
# ---------------------------------------------------------------------------


class TestDkimAlignment:
    """The signing domain must cover the From domain, or any signed mail passes."""

    def test_exact_match(self):
        assert _is_aligned("example.com", "example.com")

    def test_subdomain_of_signer(self):
        assert _is_aligned("example.com", "mail.example.com")

    def test_unrelated_domain(self):
        """A Gmail-signed message claiming From: ceo@yourcompany.com."""
        assert not _is_aligned("gmail.com", "yourcompany.com")

    def test_suffix_lookalike_not_aligned(self):
        """notexample.com must not count as a subdomain of example.com."""
        assert not _is_aligned("example.com", "notexample.com")

    def test_empty_signing_domain(self):
        assert not _is_aligned("", "example.com")


class TestVerifyDkim:
    RAW = b"From: alice@example.com\r\nSubject: hi\r\n\r\nbody"

    def _patch_dkim(self, verify_result, signing_domain=b"example.com"):
        verifier = MagicMock()
        verifier.verify.return_value = verify_result
        verifier.signature_fields = {b"d": signing_domain}
        module = MagicMock()
        module.DKIM.return_value = verifier
        module.DKIMException = Exception
        return patch.dict("sys.modules", {"dkim": module})

    def test_valid_and_aligned(self):
        with self._patch_dkim(True):
            ok, reason = verify_dkim(self.RAW, "alice@example.com")
        assert ok
        assert reason == ""

    def test_signature_invalid(self):
        with self._patch_dkim(False):
            ok, reason = verify_dkim(self.RAW, "alice@example.com")
        assert not ok
        assert "failed verification" in reason

    def test_valid_signature_wrong_domain(self):
        with self._patch_dkim(True, signing_domain=b"attacker.test"):
            ok, reason = verify_dkim(self.RAW, "alice@example.com")
        assert not ok
        assert "does not align" in reason


class TestSenderAuthenticationGate:
    def _make_service(self, **env_overrides):
        env = {
            "EMAIL_ADDRESS": "bot@example.com",
            "EMAIL_PASSWORD": "secret",
            "EMAIL_IMAP_HOST": "imap.example.com",
            "EMAIL_SMTP_HOST": "smtp.example.com",
            **env_overrides,
        }
        with patch.dict(os.environ, env, clear=False):
            return EmailService()

    def test_verification_on_by_default(self):
        assert self._make_service()._verify_dkim is True

    def test_verification_can_be_disabled(self):
        assert self._make_service(EMAIL_VERIFY_DKIM="false")._verify_dkim is False

    def test_missing_dependency_refuses_to_start(self):
        """Fail loudly rather than silently accepting unauthenticated mail."""
        with (
            patch.dict("sys.modules", {"dkim": None}),
            pytest.raises(RuntimeError, match="dkimpy"),
        ):
            self._make_service()

    @pytest.mark.asyncio
    async def test_unauthenticated_sender_dropped(self):
        """A spoofed From on the allowlist must not reach the agent."""
        svc = self._make_service(EMAIL_ALLOWED_USERS="alice@example.com")
        svc._dispatch_message = AsyncMock()

        await svc._handle_email(
            {
                "sender_addr": "alice@example.com",
                "sender_name": "Alice",
                "subject": "Deploy to prod",
                "message_id": "<spoof@x>",
                "in_reply_to": "",
                "body": "do the thing",
                "date": "",
                "dkim_ok": False,
                "dkim_reason": "no DKIM signature",
            }
        )
        svc._dispatch_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_verdict_is_treated_as_unauthenticated(self):
        """Absent key means the fetch path never vouched for this sender."""
        svc = self._make_service()
        svc._dispatch_message = AsyncMock()

        await svc._handle_email(
            {
                "sender_addr": "alice@example.com",
                "sender_name": "Alice",
                "subject": "Hi",
                "message_id": "<none@x>",
                "in_reply_to": "",
                "body": "hello",
                "date": "",
            }
        )
        svc._dispatch_message.assert_not_called()
