# Copyright (C) 2025 Codeligence
#
# This file is part of Dev Agents.
#
# Dev Agents is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Dev Agents is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Dev Agents.  If not, see <https://www.gnu.org/licenses/>.


from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import datetime

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)


class BaseMessage(ABC):
    """Abstract base class for messages from various sources."""

    @abstractmethod
    def get_user_name(self) -> str:
        """Get the display name of the message sender."""
        pass

    @abstractmethod
    def get_user_id(self) -> str:
        """Get the unique identifier of the message sender."""
        pass

    @abstractmethod
    def get_message_content(self) -> str:
        """Get the text content of the message."""
        pass

    @abstractmethod
    def get_message_date(self) -> datetime:
        """Get the timestamp when the message was sent."""
        pass

    @abstractmethod
    def get_thread_id(self) -> str:
        """Get the unique identifier of the thread this message belongs to."""
        pass

    @abstractmethod
    def is_bot(self) -> bool:
        """Check if this message was sent by a bot."""
        pass

    def get_formatted_message(self) -> str:
        """Return formatted message string with timestamp and user info."""
        if self.is_bot():
            return self.get_message_content()
        else:
            formatted_date = self.get_message_date().strftime("%Y-%m-%d %H:%M")
            return f"From {self.get_user_name()} ({formatted_date}):\n{self.get_message_content()}"


class MessageList:
    """Container for grouped messages with filtering capabilities."""

    def __init__(self, messages: list[BaseMessage] | None = None):
        self._messages = messages or []

    def add_message(self, message: BaseMessage) -> None:
        """Add a message to the list."""
        self._messages.append(message)

    def get_messages(self) -> list[BaseMessage]:
        """Get all messages in the list."""
        return self._messages.copy()

    def filter_by_thread_id(self, thread_id: str) -> "MessageList":
        """Return a new MessageList containing only messages from the specified thread."""
        filtered_messages = [
            msg for msg in self._messages if msg.get_thread_id() == thread_id
        ]
        return MessageList(filtered_messages)

    def group_by_thread_id(self) -> dict[str, "MessageList"]:
        """Group messages by thread ID and return a dictionary of thread_id -> MessageList."""
        groups = {}
        for message in self._messages:
            thread_id = message.get_thread_id()
            if thread_id not in groups:
                groups[thread_id] = MessageList()
            groups[thread_id].add_message(message)
        return groups

    def get_thread_ids(self) -> list[str]:
        """Get all unique thread IDs in the message list."""
        return list({msg.get_thread_id() for msg in self._messages})

    def __len__(self) -> int:
        return len(self._messages)

    def __bool__(self) -> bool:
        return bool(self._messages)

    def __iter__(self) -> Iterator[BaseMessage]:
        return iter(self._messages)

    def to_pydantic_chat_history(self) -> list[ModelRequest | ModelResponse]:
        """Convert messages to Pydantic AI chat history format with alternating structure.

        Groups consecutive messages by role (user vs bot) and creates alternating
        ModelRequest and ModelResponse objects as required by models like Claude.

        Returns:
            List of alternating ModelRequest and ModelResponse objects
        """
        if not self._messages:
            return []

        history = []
        current_group = []
        current_is_bot = None

        # Group consecutive messages by role
        for message in self._messages:
            is_bot = message.is_bot()

            if current_is_bot is None or current_is_bot == is_bot:
                # Same role or first message, add to current group
                current_group.append(message)
                current_is_bot = is_bot
            else:
                # Role changed, process current group and start new one
                if current_group:
                    history.append(
                        self._create_message_part(
                            current_group, current_is_bot or False
                        )
                    )
                current_group = [message]
                current_is_bot = is_bot

        # Process the last group
        if current_group:
            history.append(
                self._create_message_part(current_group, current_is_bot or False)
            )

        return history

    def _create_message_part(
        self, messages: list[BaseMessage], is_bot: bool
    ) -> ModelRequest | ModelResponse:
        """Create ModelRequest or ModelResponse from a group of messages with same role."""
        if is_bot:
            # Bot messages become ModelResponse with list of TextPart
            text_parts = [
                TextPart(content=msg.get_formatted_message()) for msg in messages
            ]
            return ModelResponse(parts=text_parts)  # type: ignore[arg-type]
        else:
            # User messages become ModelRequest with list of UserPromptPart
            user_parts = [
                UserPromptPart(content=msg.get_formatted_message()) for msg in messages
            ]
            return ModelRequest(parts=user_parts)  # type: ignore[arg-type]
