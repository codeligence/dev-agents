"""Tests for PlatformMessage and BasePlatformService."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch
import asyncio
import os

import pytest

from integrations.platforms.base import BasePlatformService, PlatformMessage

# ---------------------------------------------------------------------------
# PlatformMessage tests
# ---------------------------------------------------------------------------


class TestPlatformMessage:
    def test_basic_fields(self):
        msg = PlatformMessage(
            user_name="Alice",
            user_id="U123",
            content="Hello world",
            date=datetime(2025, 1, 1, 12, 0, 0, tzinfo=UTC),
            platform_name="test",
        )
        assert msg.get_user_id() == "U123"
        assert msg.content == "Hello world"
        assert msg.is_bot() is False
        assert msg.platform_name == "test"

    def test_bot_message(self):
        msg = PlatformMessage(
            user_name="Bot",
            user_id="B1",
            content="Reply",
            date=datetime(2025, 1, 1, tzinfo=UTC),
            is_bot=True,
        )
        assert msg.is_bot() is True

    def test_formatted_message(self):
        msg = PlatformMessage(
            user_name="Bob",
            user_id="U456",
            content="Test message",
            date=datetime(2025, 6, 15, 14, 30, 0, tzinfo=UTC),
            platform_name="email",
        )
        formatted = msg.get_formatted_message()
        assert "Bob" in formatted
        assert "email" in formatted
        assert "Test message" in formatted
        assert "2025-06-15" in formatted

    def test_naive_datetime_gets_utc(self):
        msg = PlatformMessage(
            user_name="X",
            user_id="X",
            content="",
            date=datetime(2025, 1, 1, 12, 0, 0),  # naive
        )
        assert msg.get_message_date().tzinfo is not None

    def test_thread_and_channel(self):
        msg = PlatformMessage(
            user_name="X",
            user_id="X",
            content="",
            date=datetime(2025, 1, 1, tzinfo=UTC),
            thread_id="T1",
            channel_id="C1",
        )
        assert msg.thread_id == "T1"
        assert msg.channel_id == "C1"


# ---------------------------------------------------------------------------
# BasePlatformService tests
# ---------------------------------------------------------------------------


class ConcreteService(BasePlatformService):
    """Minimal concrete implementation for testing."""

    def __init__(self):
        super().__init__("test")
        self.connected = False
        self.sent_messages = []

    async def connect(self):
        self.connected = True
        return True

    async def disconnect(self):
        self.connected = False

    async def send_response(self, chat_id, thread_id, text):
        self.sent_messages.append((chat_id, thread_id, text))
        return f"msg-{len(self.sent_messages)}"


class TestBasePlatformService:
    def test_truncate_short_message(self):
        chunks = BasePlatformService.truncate_message("short", 100)
        assert chunks == ["short"]

    def test_truncate_long_message(self):
        text = "line\n" * 100
        chunks = BasePlatformService.truncate_message(text, 50)
        assert len(chunks) > 1
        assert all(len(c) <= 50 for c in chunks)

    def test_truncate_no_newlines(self):
        text = "x" * 200
        chunks = BasePlatformService.truncate_message(text, 100)
        assert len(chunks) == 2
        assert chunks[0] == "x" * 100
        assert chunks[1] == "x" * 100

    def test_get_authorized_ids_empty(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TEST_AUTH", None)
            result = BasePlatformService.get_authorized_ids("TEST_AUTH")
            assert result is None

    def test_get_authorized_ids_set(self):
        with patch.dict(os.environ, {"TEST_AUTH": "a, b, c"}):
            result = BasePlatformService.get_authorized_ids("TEST_AUTH")
            assert result == {"a", "b", "c"}

    def test_get_authorized_ids_whitespace_only(self):
        with patch.dict(os.environ, {"TEST_AUTH": "  "}):
            result = BasePlatformService.get_authorized_ids("TEST_AUTH")
            assert result is None

    @pytest.mark.asyncio
    async def test_dispatch_message(self):
        svc = ConcreteService()
        mock_agent_service = AsyncMock()
        svc.set_agent_service(mock_agent_service)

        msg = PlatformMessage(
            user_name="Alice",
            user_id="U1",
            content="Hello",
            date=datetime(2025, 1, 1, tzinfo=UTC),
            channel_id="C1",
            thread_id="T1",
        )
        await svc._dispatch_message(msg)
        mock_agent_service.execute_agent_by_type.assert_called_once()
        call_args = mock_agent_service.execute_agent_by_type.call_args
        assert call_args[0][0] == "gitchatbot"
        context = call_args[0][1]
        assert context.get_execution_id() == "T1"

    @pytest.mark.asyncio
    async def test_dispatch_without_agent_service(self):
        svc = ConcreteService()
        msg = PlatformMessage(
            user_name="X",
            user_id="X",
            content="",
            date=datetime(2025, 1, 1, tzinfo=UTC),
        )
        # Should not raise — just logs error
        await svc._dispatch_message(msg)

    @pytest.mark.asyncio
    async def test_start_stop(self):
        svc = ConcreteService()

        # Override connect to block briefly then return
        async def _connect():
            await asyncio.sleep(0.05)
            return True

        svc.connect = _connect

        await svc.start()
        assert svc._running is True
        assert svc._task is not None

        await svc.stop()
        assert svc._running is False
