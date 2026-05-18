"""Tests for PlatformAgentContext."""

from datetime import datetime, timezone

import pytest

from integrations.platforms.agent_context import PlatformAgentContext
from integrations.platforms.base import BasePlatformService, PlatformMessage


class FireAndForgetService(BasePlatformService):
    """Platform that does not support edits — mirrors email."""

    supports_updates = False

    def __init__(self):
        super().__init__("fire")
        self.sent_messages: list[tuple[str, str, str]] = []
        self._next_id = 0

    async def connect(self):
        return True

    async def disconnect(self):
        pass

    async def send_response(self, chat_id, thread_id, text):
        self._next_id += 1
        self.sent_messages.append((chat_id, thread_id, text))
        return f"msg-{self._next_id}"


class EditableService(BasePlatformService):
    """Platform that supports edits — mirrors telegram/mattermost."""

    supports_updates = True

    def __init__(self):
        super().__init__("editable")
        self.sent_messages: list[tuple[str, str, str]] = []
        self.updated_messages: list[tuple[str, str, str]] = []
        self._next_id = 0
        self.fail_next_update = False

    async def connect(self):
        return True

    async def disconnect(self):
        pass

    async def send_response(self, chat_id, thread_id, text):
        self._next_id += 1
        msg_id = f"msg-{self._next_id}"
        self.sent_messages.append((chat_id, thread_id, text))
        return msg_id

    async def update_response(self, chat_id, message_id, text):
        if self.fail_next_update:
            self.fail_next_update = False
            return False
        self.updated_messages.append((chat_id, message_id, text))
        return True


def _make_message(**kwargs):
    defaults = dict(
        user_name="Alice",
        user_id="U1",
        content="Hello",
        date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        channel_id="C1",
        thread_id="T1",
        platform_name="test",
    )
    defaults.update(kwargs)
    return PlatformMessage(**defaults)


class TestPlatformAgentContext:
    def test_init(self):
        svc = FireAndForgetService()
        msg = _make_message()
        ctx = PlatformAgentContext(
            platform_service=svc,
            chat_id="C1",
            thread_id="T1",
            messages=[msg],
        )
        assert ctx.get_execution_id() == "T1"
        assert ctx.get_context_id() is not None

    def test_execution_id_falls_back_to_chat_id(self):
        svc = FireAndForgetService()
        ctx = PlatformAgentContext(
            platform_service=svc,
            chat_id="C1",
            thread_id="",
            messages=[],
        )
        assert ctx.get_execution_id() == "C1"

    def test_get_message_list(self):
        svc = FireAndForgetService()
        msg = _make_message()
        ctx = PlatformAgentContext(
            platform_service=svc,
            chat_id="C1",
            thread_id="T1",
            messages=[msg],
        )
        ml = ctx.get_message_list()
        assert len(ml) == 1

    def test_get_config_and_prompts(self):
        svc = FireAndForgetService()
        ctx = PlatformAgentContext(
            platform_service=svc,
            chat_id="C1",
            thread_id="T1",
            messages=[],
        )
        assert ctx.get_config() is not None
        assert ctx.get_prompts() is not None

    # -- Fire-and-forget platform (email) -----------------------------------

    @pytest.mark.asyncio
    async def test_fire_and_forget_sends_response(self):
        svc = FireAndForgetService()
        ctx = PlatformAgentContext(
            platform_service=svc,
            chat_id="C1",
            thread_id="T1",
            messages=[],
        )
        await ctx.send_response("Hello back")
        assert ("C1", "T1", "Hello back") in svc.sent_messages

    @pytest.mark.asyncio
    async def test_fire_and_forget_skips_status(self):
        """Email-like platforms skip status updates entirely."""
        svc = FireAndForgetService()
        ctx = PlatformAgentContext(
            platform_service=svc,
            chat_id="C1",
            thread_id="T1",
            messages=[],
        )
        await ctx.send_status("Working...")
        await ctx.send_status("Still working...")
        assert svc.sent_messages == []

    @pytest.mark.asyncio
    async def test_fire_and_forget_final_response_after_skipped_status(self):
        svc = FireAndForgetService()
        ctx = PlatformAgentContext(
            platform_service=svc,
            chat_id="C1",
            thread_id="T1",
            messages=[],
        )
        await ctx.send_status("Working...")
        await ctx.send_response("Done!")
        assert svc.sent_messages == [("C1", "T1", "Done!")]

    # -- Editable platform (telegram/mattermost) ----------------------------

    @pytest.mark.asyncio
    async def test_editable_first_status_sends_new(self):
        svc = EditableService()
        ctx = PlatformAgentContext(
            platform_service=svc,
            chat_id="C1",
            thread_id="T1",
            messages=[],
        )
        await ctx.send_status("Working...")
        assert len(svc.sent_messages) == 1
        assert svc.updated_messages == []

    @pytest.mark.asyncio
    async def test_editable_subsequent_status_edits_existing(self):
        svc = EditableService()
        ctx = PlatformAgentContext(
            platform_service=svc,
            chat_id="C1",
            thread_id="T1",
            messages=[],
        )
        await ctx.send_status("Step 1")
        await ctx.send_status("Step 2")
        assert len(svc.sent_messages) == 1
        assert len(svc.updated_messages) == 1
        assert svc.updated_messages[0][2] == "Step 2"

    @pytest.mark.asyncio
    async def test_editable_response_after_status_edits_same_message(self):
        svc = EditableService()
        ctx = PlatformAgentContext(
            platform_service=svc,
            chat_id="C1",
            thread_id="T1",
            messages=[],
        )
        await ctx.send_status("Working...")
        await ctx.send_response("Done!")
        assert len(svc.sent_messages) == 1
        assert len(svc.updated_messages) == 1
        assert svc.updated_messages[0][2] == "Done!"

    @pytest.mark.asyncio
    async def test_editable_response_after_response_sends_new(self):
        """A final response clears the tracked ID, so next one sends new."""
        svc = EditableService()
        ctx = PlatformAgentContext(
            platform_service=svc,
            chat_id="C1",
            thread_id="T1",
            messages=[],
        )
        await ctx.send_response("First")
        await ctx.send_response("Second")
        assert len(svc.sent_messages) == 2
        assert svc.updated_messages == []

    @pytest.mark.asyncio
    async def test_editable_falls_back_to_new_when_update_fails(self):
        svc = EditableService()
        ctx = PlatformAgentContext(
            platform_service=svc,
            chat_id="C1",
            thread_id="T1",
            messages=[],
        )
        await ctx.send_status("Step 1")
        svc.fail_next_update = True
        await ctx.send_status("Step 2")
        assert len(svc.sent_messages) == 2
        assert svc.updated_messages == []

    @pytest.mark.asyncio
    async def test_editable_send_attachment_text(self):
        svc = EditableService()
        ctx = PlatformAgentContext(
            platform_service=svc,
            chat_id="C1",
            thread_id="T1",
            messages=[],
        )
        await ctx.send_attachment("report.md", "# Report\nContent here")
        assert len(svc.sent_messages) == 1
        assert "**report.md**" in svc.sent_messages[0][2]
        assert "Content here" in svc.sent_messages[0][2]

    @pytest.mark.asyncio
    async def test_send_attachment_binary_raises(self):
        svc = FireAndForgetService()
        ctx = PlatformAgentContext(
            platform_service=svc,
            chat_id="C1",
            thread_id="T1",
            messages=[],
        )
        with pytest.raises(NotImplementedError):
            await ctx.send_attachment("file.bin", b"\x00\x01", is_binary=True)
