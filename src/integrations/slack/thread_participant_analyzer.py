"""Thread participant analyzer for Slack message filtering."""

from typing import Any
import re


class ThreadParticipantAnalyzer:
    """Extracts participants from thread messages. Stateless.

    A participant is:
    - A user who sent a message
    - A user who was mentioned (@user)
    """

    USER_MENTION_PATTERN = re.compile(r"<@(U[A-Z0-9]+)>")

    def __init__(self, bot_id: str):
        self.bot_id = bot_id

    def get_participants(self, messages: list[dict[str, Any]]) -> set[str]:
        """Extract all human participants from messages."""
        participants: set[str] = set()

        for msg in messages:
            sender = msg.get("user")
            if sender and sender != self.bot_id:
                participants.add(sender)

            text = msg.get("text", "")
            for match in self.USER_MENTION_PATTERN.finditer(text):
                user_id = match.group(1)
                if user_id != self.bot_id:
                    participants.add(user_id)

        return participants
