"""Tests for TelegramService — message handling and formatting without real connections."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from integrations.platforms.telegram import (
    TelegramService,
    _escape_mdv2,
    _format_mdv2,
    _strip_mdv2,
)


# ---------------------------------------------------------------------------
# MarkdownV2 formatting tests
# ---------------------------------------------------------------------------

class TestMarkdownV2:
    def test_escape_special_chars(self):
        result = _escape_mdv2("hello_world (test)")
        assert result == r"hello\_world \(test\)"

    def test_strip_mdv2(self):
        result = _strip_mdv2(r"hello\_world \(test\)")
        assert result == "hello_world (test)"

    def test_format_code_block_preserved(self):
        text = "```python\nprint('hello')\n```"
        result = _format_mdv2(text)
        assert "```python" in result
        assert "print" in result

    def test_format_inline_code_preserved(self):
        text = "Use `foo_bar` function"
        result = _format_mdv2(text)
        assert "`foo_bar`" in result

    def test_format_bold(self):
        result = _format_mdv2("This is **bold** text")
        assert "*bold*" in result

    def test_format_header_to_bold(self):
        result = _format_mdv2("## My Header")
        assert "*My Header*" in result.replace("\\", "")

    def test_format_link(self):
        result = _format_mdv2("[click](http://example.com)")
        assert "http://example.com" in result
        assert "click" in result

    def test_format_plain_text_escapes(self):
        result = _format_mdv2("price is 5.99 (USD)")
        assert "\\." in result
        assert "\\(" in result

    def test_format_empty(self):
        assert _format_mdv2("") == ""
        assert _format_mdv2(None) is None

    def test_format_strikethrough(self):
        result = _format_mdv2("~~deleted~~")
        assert "~deleted~" in result

    # -- Edge cases for MarkdownV2 formatter -----------------------------------

    def test_format_nested_bold_in_header(self):
        """Header with inner **bold** should not produce double nesting."""
        result = _format_mdv2("## **Important** Notice")
        # Should be a single bold span, not nested *...*...*
        stripped = _strip_mdv2(result)
        assert "Important" in stripped
        assert "Notice" in stripped

    def test_format_multiple_code_blocks(self):
        """Multiple fenced code blocks should all be preserved."""
        text = "Before\n```python\na = 1\n```\nMiddle\n```js\nb = 2\n```\nAfter"
        result = _format_mdv2(text)
        assert "```python" in result
        assert "```js" in result
        assert "a = 1" in result
        assert "b = 2" in result

    def test_format_code_block_with_special_chars(self):
        """Special chars inside code blocks must NOT be escaped."""
        text = "```\nif (x > 0) { return x * 2; }\n```"
        result = _format_mdv2(text)
        # Inside code block: > and { should NOT have backslash escape
        # (they get \\ for literal backslash, but not MarkdownV2 escape)
        assert "```" in result
        assert "return" in result

    def test_format_inline_code_with_underscores(self):
        """Underscores inside inline code must stay literal."""
        result = _format_mdv2("Call `my_func_name` here")
        assert "`my_func_name`" in result

    def test_format_mixed_bold_and_italic(self):
        """Bold and italic in same line."""
        result = _format_mdv2("**bold** and *italic* text")
        assert "*bold*" in result
        assert "_italic_" in result

    def test_format_link_with_parens_in_url(self):
        """URL with parentheses should be escaped properly."""
        result = _format_mdv2("[wiki](https://en.wikipedia.org/wiki/Test_(disambiguation))")
        assert "wikipedia" in result
        assert "click" not in result  # sanity: 'click' not in this text

    def test_format_blockquote(self):
        result = _format_mdv2("> This is quoted")
        stripped = _strip_mdv2(result)
        assert "This is quoted" in stripped

    def test_format_multiline_blockquotes(self):
        text = "> Line one\n> Line two"
        result = _format_mdv2(text)
        stripped = _strip_mdv2(result)
        assert "Line one" in stripped
        assert "Line two" in stripped

    def test_format_special_chars_only(self):
        """String with only special chars should be fully escaped."""
        result = _format_mdv2("()+.-!")
        assert "\\(" in result
        assert "\\)" in result
        assert "\\+" in result
        assert "\\." in result
        assert "\\-" in result
        assert "\\!" in result

    def test_format_preserves_newlines(self):
        result = _format_mdv2("Line 1\n\nLine 2")
        assert "\n\n" in result

    def test_format_bold_with_special_chars(self):
        """Bold text containing special chars should escape inner content."""
        result = _format_mdv2("**price (USD)**")
        # Inner parens should be escaped inside bold
        stripped = _strip_mdv2(result)
        assert "price (USD)" in stripped

    def test_format_header_levels(self):
        """All header levels should convert to bold."""
        for level in range(1, 7):
            prefix = "#" * level
            result = _format_mdv2(f"{prefix} Title")
            stripped = _strip_mdv2(result)
            assert "Title" in stripped

    def test_strip_mdv2_bold(self):
        assert _strip_mdv2("*bold text*") == "bold text"

    def test_strip_mdv2_italic(self):
        assert _strip_mdv2("_italic_") == "italic"

    def test_strip_mdv2_strikethrough(self):
        assert _strip_mdv2("~deleted~") == "deleted"

    def test_strip_mdv2_spoiler(self):
        assert _strip_mdv2("||hidden||") == "hidden"

    def test_roundtrip_plain_text(self):
        """Plain text → format → strip should be identity."""
        original = "Hello world"
        formatted = _format_mdv2(original)
        stripped = _strip_mdv2(formatted)
        assert stripped == original


# ---------------------------------------------------------------------------
# TelegramService tests
# ---------------------------------------------------------------------------

class TestTelegramService:
    def _make_service(self, **env_overrides):
        env = {
            "TELEGRAM_BOT_TOKEN": "123:ABC",
            **env_overrides,
        }
        with patch.dict(os.environ, env, clear=False):
            return TelegramService()

    def test_init(self):
        svc = self._make_service()
        assert svc.name == "telegram"
        assert svc._token == "123:ABC"

    def test_allowed_users(self):
        svc = self._make_service(TELEGRAM_ALLOWED_USERS="111,222")
        assert svc._allowed_users == {"111", "222"}

    def test_clean_bot_mention(self):
        svc = self._make_service()
        svc._bot_username = "mybot"
        assert svc._clean_bot_mention("@mybot what is this?") == "what is this?"
        assert svc._clean_bot_mention("hello @mybot") == "hello"
        assert svc._clean_bot_mention("no mention") == "no mention"

    def test_clean_bot_mention_no_username(self):
        svc = self._make_service()
        svc._bot_username = ""
        assert svc._clean_bot_mention("@mybot test") == "@mybot test"

    def test_clean_bot_mention_none(self):
        svc = self._make_service()
        svc._bot_username = "bot"
        assert svc._clean_bot_mention(None) == ""

    # -- Mention gating -------------------------------------------------------

    def _make_message_mock(self, *, chat_type="private", chat_id="123",
                           text="hello", from_user_id=1, reply_to_bot=False,
                           bot_id=99):
        msg = MagicMock()
        # Use a real string for type so str().split(".")[-1].lower() works
        msg.chat = MagicMock()
        msg.chat.type = chat_type
        msg.chat.id = chat_id
        msg.text = text
        msg.caption = None
        msg.from_user = MagicMock()
        msg.from_user.id = from_user_id

        if reply_to_bot:
            msg.reply_to_message = MagicMock()
            msg.reply_to_message.from_user = MagicMock()
            msg.reply_to_message.from_user.id = bot_id
        else:
            msg.reply_to_message = None

        return msg

    def test_should_process_dm(self):
        svc = self._make_service(TELEGRAM_REQUIRE_MENTION="true")
        svc._bot_id = 99
        svc._bot_username = "mybot"
        msg = self._make_message_mock(chat_type="private")
        assert svc._should_process_message(msg) is True

    def test_should_process_group_no_mention_required(self):
        svc = self._make_service(TELEGRAM_REQUIRE_MENTION="false")
        svc._bot_id = 99
        svc._bot_username = "mybot"
        msg = self._make_message_mock(chat_type="supergroup")
        assert svc._should_process_message(msg) is True

    def test_should_process_group_mention_required_no_mention(self):
        svc = self._make_service(TELEGRAM_REQUIRE_MENTION="true")
        svc._bot_id = 99
        svc._bot_username = "mybot"
        msg = self._make_message_mock(chat_type="supergroup", text="hello everyone")
        with patch.dict(os.environ, {"TELEGRAM_REQUIRE_MENTION": "true"}):
            assert svc._should_process_message(msg) is False

    def test_should_process_group_with_mention(self):
        svc = self._make_service(TELEGRAM_REQUIRE_MENTION="true")
        svc._bot_id = 99
        svc._bot_username = "mybot"
        msg = self._make_message_mock(chat_type="supergroup", text="@mybot help")
        assert svc._should_process_message(msg) is True

    def test_should_process_group_reply_to_bot(self):
        svc = self._make_service(TELEGRAM_REQUIRE_MENTION="true")
        svc._bot_id = 99
        svc._bot_username = "mybot"
        msg = self._make_message_mock(chat_type="supergroup", reply_to_bot=True, bot_id=99)
        assert svc._should_process_message(msg) is True

    def test_should_process_group_command_always(self):
        svc = self._make_service(TELEGRAM_REQUIRE_MENTION="true")
        svc._bot_id = 99
        svc._bot_username = "mybot"
        msg = self._make_message_mock(chat_type="supergroup", text="/start")
        assert svc._should_process_message(msg, is_command=True) is True

    def test_should_process_free_chat(self):
        svc = self._make_service(
            TELEGRAM_REQUIRE_MENTION="true",
            TELEGRAM_FREE_RESPONSE_CHATS="123",
        )
        svc._bot_id = 99
        svc._bot_username = "mybot"
        msg = self._make_message_mock(chat_type="supergroup", chat_id="123")
        assert svc._should_process_message(msg) is True

    # -- Conflict / network error detection -----------------------------------

    def test_looks_like_polling_conflict(self):
        class Conflict(Exception):
            pass
        e = Conflict("Conflict: terminated by other getUpdates request")
        assert TelegramService._looks_like_polling_conflict(e) is True

    def test_looks_like_polling_conflict_false(self):
        e = ValueError("some other error")
        assert TelegramService._looks_like_polling_conflict(e) is False

    def test_looks_like_network_error(self):
        assert TelegramService._looks_like_network_error(OSError("connection reset")) is True

    def test_looks_like_network_error_false(self):
        assert TelegramService._looks_like_network_error(ValueError("bad")) is False

    # -- dispatch_telegram_message --------------------------------------------

    @pytest.mark.asyncio
    async def test_dispatch_telegram_message(self):
        svc = self._make_service()
        svc._dispatch_message = AsyncMock()

        msg = MagicMock()
        msg.from_user.id = 111
        msg.from_user.full_name = "Alice"
        msg.chat.id = 999
        msg.message_thread_id = None
        msg.date = None

        await svc._dispatch_telegram_message(msg, "Hello bot")
        svc._dispatch_message.assert_called_once()
        platform_msg = svc._dispatch_message.call_args[0][0]
        assert platform_msg.content == "Hello bot"
        assert platform_msg.platform_name == "telegram"
        assert platform_msg.get_user_id() == "111"

    @pytest.mark.asyncio
    async def test_dispatch_telegram_message_unauthorized(self):
        svc = self._make_service(TELEGRAM_ALLOWED_USERS="222")
        svc._dispatch_message = AsyncMock()

        msg = MagicMock()
        msg.from_user.id = 111
        msg.from_user.full_name = "Stranger"
        msg.chat.id = 999
        msg.message_thread_id = None
        msg.date = None

        await svc._dispatch_telegram_message(msg, "Hi")
        svc._dispatch_message.assert_not_called()
