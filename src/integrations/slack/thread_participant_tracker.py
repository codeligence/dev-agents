"""Tracks thread participants with per-thread persistent storage."""

from typing import Any

from core.log import get_logger
from core.storage import BaseStorage, get_storage
from integrations.slack.thread_participant_analyzer import ThreadParticipantAnalyzer


def _storage_key(thread_id: str) -> str:
    return f"slack_thread_{thread_id}"


class ThreadParticipantTracker:
    """Manages per-thread participant storage.

    Each thread has its own storage file containing participant list.
    No file = not a bot conversation.
    """

    def __init__(
        self,
        bot_id: str,
        storage: BaseStorage | None = None,
    ):
        self.logger = get_logger("ThreadParticipantTracker")
        self._storage = storage or get_storage()
        self._analyzer = ThreadParticipantAnalyzer(bot_id)

    def register_thread(self, thread_id: str, sender_id: str) -> None:
        """Register new bot conversation with initial participant."""
        key = _storage_key(thread_id)
        self._storage.set(key, [sender_id])
        self.logger.info(f"Registered thread {thread_id} with participant {sender_id}")

    def is_registered(self, thread_id: str) -> bool:
        """Check if thread is a registered bot conversation."""
        key = _storage_key(thread_id)
        participants = self._storage.get(key)
        return participants is not None

    def get_participant_count(self, thread_id: str) -> int:
        """Get cached participant count for thread."""
        key = _storage_key(thread_id)
        participants = self._storage.get(key, [])
        return len(participants)

    def update_participants(self, thread_id: str, participants: set[str]) -> None:
        """Update stored participants for thread."""
        key = _storage_key(thread_id)
        self._storage.set(key, list(participants))
        self.logger.debug(
            f"Updated thread {thread_id} participants: {len(participants)}"
        )

    def extract_participants(self, messages: list[dict[str, Any]]) -> set[str]:
        """Extract participants from messages (delegates to analyzer)."""
        return self._analyzer.get_participants(messages)
