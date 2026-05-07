from dataclasses import dataclass
from datetime import datetime

from core.message import BaseMessage


@dataclass
class SlackMessage(BaseMessage):
    """Concrete implementation of BaseMessage for Slack messages."""

    channel_id: str
    message_id: str  # Slack timestamp
    user_id: str
    username: str
    content: str
    timestamp: datetime
    thread_ts: str
    is_from_bot: bool = False

    def get_user_name(self) -> str:
        return self.username

    def get_user_id(self) -> str:
        return self.user_id

    def get_message_content(self) -> str:
        return self.content

    def get_message_date(self) -> datetime:
        return self.timestamp

    def get_thread_id(self) -> str:
        return self.thread_ts

    def is_bot(self) -> bool:
        return self.is_from_bot
