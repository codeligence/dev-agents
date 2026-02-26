from unittest.mock import MagicMock, patch

import pytest

from integrations.slack.slack_client_service import (
    SlackClientService,
    ThreadReplyDecision,
)


class TestShouldProcessThreadReply:
    """Test cases for should_process_thread_reply method."""

    @pytest.fixture
    def mock_tracker(self) -> MagicMock:
        """Create a mock participant tracker."""
        tracker = MagicMock()
        tracker.is_registered.return_value = False
        tracker.get_participant_count.return_value = 0
        tracker.extract_participants.return_value = []
        return tracker

    @pytest.fixture
    def service(self, mock_tracker: MagicMock) -> SlackClientService:
        """Create SlackClientService with mocked dependencies."""
        with patch.object(SlackClientService, "__init__", lambda _self: None):
            svc = SlackClientService()
            svc._participant_tracker = mock_tracker
            svc.bot_id = "BOT123"
            svc.log = MagicMock()
            svc.is_bot_mentioned = MagicMock(return_value=False)
            svc.get_thread_conversation = MagicMock(return_value=[])
            svc._update_participants = MagicMock()
            svc._register_thread_from_conversation = MagicMock()
            return svc

    # --- No tracker fallback ---
    def test_no_tracker_always_processes(self, service: SlackClientService) -> None:
        """Without tracker, always process."""
        service._participant_tracker = None

        result = service.should_process_thread_reply("t1", "c1", "hello")

        assert result.should_process is True
        assert result.conversation is None

    # --- Bot mentioned scenarios ---
    def test_bot_mentioned_in_unregistered_thread_processes_and_registers(
        self, service: SlackClientService, mock_tracker: MagicMock
    ) -> None:
        """Bot mention in unregistered thread: process + register."""
        service.is_bot_mentioned.return_value = True
        mock_tracker.is_registered.return_value = False
        conversation = [{"user": "U1", "text": "hi <@BOT123>"}]
        service.get_thread_conversation.return_value = conversation

        result = service.should_process_thread_reply("t1", "c1", "hi <@BOT123>")

        assert result.should_process is True
        assert result.conversation == conversation
        service._register_thread_from_conversation.assert_called_once()
        service._update_participants.assert_called_once()

    def test_bot_mentioned_in_registered_thread_processes(
        self, service: SlackClientService, mock_tracker: MagicMock
    ) -> None:
        """Bot mention in registered thread: process without re-registering."""
        service.is_bot_mentioned.return_value = True
        mock_tracker.is_registered.return_value = True
        conversation = [{"user": "U1", "text": "hi <@BOT123>"}]
        service.get_thread_conversation.return_value = conversation

        result = service.should_process_thread_reply("t1", "c1", "hi <@BOT123>")

        assert result.should_process is True
        assert result.conversation == conversation
        service._register_thread_from_conversation.assert_not_called()

    # --- No mention, unregistered ---
    def test_unregistered_thread_no_mention_skips(
        self, service: SlackClientService, mock_tracker: MagicMock
    ) -> None:
        """No mention + not registered = skip."""
        service.is_bot_mentioned.return_value = False
        mock_tracker.is_registered.return_value = False

        result = service.should_process_thread_reply("t1", "c1", "hello")

        assert result.should_process is False
        assert result.conversation is None
        service.get_thread_conversation.assert_not_called()

    # --- Registered, no mention, participant checks ---
    def test_registered_two_plus_cached_participants_skips(
        self, service: SlackClientService, mock_tracker: MagicMock
    ) -> None:
        """Registered + 2+ cached participants + no mention = skip (fast path)."""
        service.is_bot_mentioned.return_value = False
        mock_tracker.is_registered.return_value = True
        mock_tracker.get_participant_count.return_value = 2

        result = service.should_process_thread_reply("t1", "c1", "hello")

        assert result.should_process is False
        service.get_thread_conversation.assert_not_called()

    def test_registered_one_participant_processes(
        self, service: SlackClientService, mock_tracker: MagicMock
    ) -> None:
        """Registered + 1 participant (private) = process."""
        service.is_bot_mentioned.return_value = False
        mock_tracker.is_registered.return_value = True
        mock_tracker.get_participant_count.return_value = 1
        mock_tracker.extract_participants.return_value = ["U1"]
        conversation = [{"user": "U1", "text": "hello"}]
        service.get_thread_conversation.return_value = conversation

        result = service.should_process_thread_reply("t1", "c1", "hello")

        assert result.should_process is True
        assert result.conversation == conversation

    def test_registered_one_cached_but_two_actual_skips(
        self, service: SlackClientService, mock_tracker: MagicMock
    ) -> None:
        """1 cached but 2 actual participants after loading = skip."""
        service.is_bot_mentioned.return_value = False
        mock_tracker.is_registered.return_value = True
        mock_tracker.get_participant_count.return_value = 1
        mock_tracker.extract_participants.return_value = ["U1", "U2"]
        conversation = [{"user": "U1"}, {"user": "U2"}]
        service.get_thread_conversation.return_value = conversation

        result = service.should_process_thread_reply("t1", "c1", "hello")

        assert result.should_process is False


class TestThreadReplyDecisionDataclass:
    """Test ThreadReplyDecision dataclass."""

    def test_defaults(self) -> None:
        """Test default values."""
        decision = ThreadReplyDecision(should_process=True)
        assert decision.should_process is True
        assert decision.conversation is None

    def test_with_conversation(self) -> None:
        """Test with conversation."""
        conv = [{"user": "U1"}]
        decision = ThreadReplyDecision(should_process=True, conversation=conv)
        assert decision.conversation == conv
