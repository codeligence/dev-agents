from unittest.mock import AsyncMock, MagicMock

import pytest

from entrypoints.slack_entrypoint.stop_command_handler import StopCommandHandler


@pytest.fixture
def slack_service() -> MagicMock:
    svc = MagicMock()
    svc.is_bot_mentioned = MagicMock(return_value=False)
    svc.send_reply = AsyncMock()
    return svc


@pytest.fixture
def task_manager() -> MagicMock:
    mgr = MagicMock()
    mgr.cancel_task.return_value = True
    return mgr


@pytest.fixture
def handler(slack_service: MagicMock, task_manager: MagicMock) -> StopCommandHandler:
    return StopCommandHandler(slack_service=slack_service, task_manager=task_manager)


class TestRequireMentionDefault:
    """Default behavior keeps the historical mention requirement."""

    def test_no_mention_rejects(
        self, handler: StopCommandHandler, slack_service: MagicMock
    ) -> None:
        slack_service.is_bot_mentioned.return_value = False
        assert handler.is_stop_command("stop", "T1", "M1") is False

    def test_mention_plus_stop_accepts(
        self, handler: StopCommandHandler, slack_service: MagicMock
    ) -> None:
        slack_service.is_bot_mentioned.return_value = True
        assert handler.is_stop_command("<@BOT123> stop", "T1", "M2") is True


class TestRequireMentionDisabled:
    """Assistant-thread / DM contexts where every message addresses the bot.

    The fix in this change: drop the mandatory ``<@BOTID>`` check so that
    plain ``stop`` cancels the in-flight task in the assistant side panel.
    """

    def test_plain_stop_accepted_without_mention(
        self, handler: StopCommandHandler, slack_service: MagicMock
    ) -> None:
        slack_service.is_bot_mentioned.return_value = False
        assert (
            handler.is_stop_command("stop", "T1", "M2", require_mention=False) is True
        )

    def test_long_message_rejected_even_without_mention(
        self, handler: StopCommandHandler
    ) -> None:
        long = "please stop processing this very long instruction now"
        assert handler.is_stop_command(long, "T1", "M2", require_mention=False) is False

    def test_message_without_stop_keyword_rejected(
        self, handler: StopCommandHandler
    ) -> None:
        assert (
            handler.is_stop_command("hello", "T1", "M2", require_mention=False) is False
        )

    def test_is_bot_mentioned_not_consulted(
        self, handler: StopCommandHandler, slack_service: MagicMock
    ) -> None:
        handler.is_stop_command("stop", "T1", "M2", require_mention=False)
        slack_service.is_bot_mentioned.assert_not_called()
