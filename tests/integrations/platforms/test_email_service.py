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
    _is_automated_sender,
    _strip_html,
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
        }
        second = {
            "sender_addr": "alice@example.com",
            "sender_name": "Alice",
            "subject": "Thread B",
            "message_id": "<b1@x>",
            "in_reply_to": "",
            "body": "Second, unrelated thread",
            "date": "",
        }
        await svc._handle_email(first)
        await svc._handle_email(second)

        ctx_a = svc._thread_context[("alice@example.com", "<a1@x>")]
        ctx_b = svc._thread_context[("alice@example.com", "<b1@x>")]
        assert ctx_a["subject"] == "Thread A"
        assert ctx_b["subject"] == "Thread B"
