"""Convert OpenAI chat messages to internal BaseMessage format."""

from dataclasses import dataclass
from datetime import datetime

from core.message import BaseMessage, MessageList
from entrypoints.openai_entrypoint.models import ChatMessage


@dataclass
class OpenAIMessage(BaseMessage):
    """BaseMessage implementation for OpenAI-format messages."""

    message_id: str
    role: str
    content: str
    thread_id: str = "default"
    timestamp: datetime | None = None

    def __post_init__(self) -> None:
        if self.timestamp is None:
            self.timestamp = datetime.now()

    # Note: after __post_init__, timestamp is always set.

    def get_user_name(self) -> str:
        if self.role == "user":
            return "User"
        elif self.role == "assistant":
            return "Assistant"
        elif self.role == "system":
            return "System"
        return self.role.title()

    def get_user_id(self) -> str:
        return f"{self.role}_{self.message_id}"

    def get_message_content(self) -> str:
        return self.content

    def get_message_date(self) -> datetime:
        return self.timestamp  # type: ignore[return-value]  # guaranteed by __post_init__

    def get_thread_id(self) -> str:
        return self.thread_id

    def is_bot(self) -> bool:
        return self.role in ("assistant", "system")


def convert_openai_messages_to_message_list(
    messages: list[ChatMessage], thread_id: str = "default"
) -> MessageList:
    """Convert OpenAI chat messages to internal MessageList.

    Args:
        messages: List of OpenAI ChatMessage objects.
        thread_id: Thread identifier for all messages.

    Returns:
        MessageList containing converted OpenAIMessage objects.
    """
    converted: list[BaseMessage] = []
    for i, msg in enumerate(messages):
        converted.append(
            OpenAIMessage(
                message_id=str(i),
                role=msg.role,
                content=msg.content,
                thread_id=thread_id,
            )
        )
    return MessageList(converted)
