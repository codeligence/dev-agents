from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from pydantic_ai import BinaryContent

from core.message import BaseMessage, UserContent
from integrations.slack.attachments import classify_attachment


@dataclass
class SlackFile:
    """A file attached to a Slack message, ready to feed to the agent.

    ``data`` holds the downloaded bytes when the file could be retrieved and is
    a type the model can consume; otherwise it is ``None`` and ``note`` explains
    why (too large, download failed, attachments disabled, …).
    """

    file_id: str
    name: str
    mimetype: str
    data: bytes | None = None
    note: str | None = None

    def to_user_content(self) -> UserContent:
        """Return the agent content part representing this attachment.

        Images and PDFs become ``BinaryContent``; text/code files are decoded
        and inlined; anything else falls back to a descriptive text marker.
        """
        if self.data is not None:
            kind = classify_attachment(self.mimetype)
            if kind == "binary":
                return BinaryContent(data=self.data, media_type=self.mimetype)
            if kind == "text":
                try:
                    text = self.data.decode("utf-8")
                    return f"[attachment: {self.name}]\n```\n{text}\n```"
                except UnicodeDecodeError:
                    return self._marker("could not decode as text")
        return self._marker(self.note)

    def _marker(self, reason: str | None) -> str:
        detail = reason or f"unsupported type {self.mimetype}"
        return f"[#attachment id={self.file_id} name={self.name} — {detail}]"


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
    files: list[SlackFile] = field(default_factory=list)

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

    def get_user_content(self) -> str | Sequence[UserContent]:
        """Return the formatted text plus any attachment content parts."""
        text = self.get_formatted_message()
        if not self.files:
            return text
        return [text, *(f.to_user_content() for f in self.files)]
