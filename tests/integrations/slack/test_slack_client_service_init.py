from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from slack_sdk.errors import SlackApiError
import pytest

from integrations.slack.slack_client_service import SlackClientService


@pytest.fixture
def slack_config() -> MagicMock:
    cfg = MagicMock()
    cfg.get_bot_token.return_value = "xoxb-test"
    cfg.get_app_token.return_value = "xapp-test"
    cfg.get_always_respond.return_value = False
    return cfg


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point file storage at a tmp dir so initialize() doesn't touch /data."""
    from core import storage as storage_mod

    monkeypatch.setenv("CORE_STORAGE_FILE_DIR", str(tmp_path))
    monkeypatch.setattr(storage_mod, "_storage_cache", {})


class TestInitializePropagatesAuthFailure:
    """``initialize()`` must surface auth failures so the runtime aborts.

    Previously the method swallowed ``SlackApiError`` and left ``bot_id``
    set to ``None``, which caused downstream filtering and participant
    tracking to silently degrade.
    """

    @pytest.mark.asyncio
    async def test_auth_test_error_propagates(self, slack_config: MagicMock) -> None:
        service = SlackClientService(slack_config)
        service.client = MagicMock()
        service.client.auth_test = AsyncMock(
            side_effect=SlackApiError(  # type: ignore[no-untyped-call]
                "auth_failed",
                response={"ok": False, "error": "invalid_auth"},
            )
        )

        with pytest.raises(SlackApiError):
            await service.initialize()

        assert service.bot_id is None
        assert service.bot_mention is None
        assert service._participant_tracker is None

    @pytest.mark.asyncio
    async def test_success_resolves_identity_and_tracker(
        self, slack_config: MagicMock
    ) -> None:
        service = SlackClientService(slack_config)
        service.client = MagicMock()
        service.client.auth_test = AsyncMock(
            return_value={"user_id": "BOT123", "user": "test-bot"}
        )

        await service.initialize()

        assert service.bot_id == "BOT123"
        assert service.bot_mention == "<@BOT123>"
        assert service._participant_tracker is not None
