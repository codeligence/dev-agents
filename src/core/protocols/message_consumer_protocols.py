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


from typing import Protocol, runtime_checkable

from core.log import get_logger
from core.message import MessageList


@runtime_checkable
class MessageConsumer(Protocol):
    """Protocol defining the interface for message consumers."""

    async def consume(self, messages: MessageList) -> None:
        """
        Process a list of messages.

        Args:
            messages: MessageList containing messages to process
        """
        ...


class DummyMessageConsumer:
    """Dummy consumer that prints received messages."""

    def __init__(self) -> None:
        self.logger = get_logger("DummyMessageConsumer")

    async def consume(self, messages: MessageList) -> None:
        """
        Process messages by printing them to the console.

        Args:
            messages: MessageList containing messages to process
        """
        self.logger.info(f"DummyMessageConsumer received {len(messages)} messages")

        if not messages:
            self.logger.info("No messages to process")
            return

        # Process messages directly (already filtered to single thread)
        if messages:
            first_message = messages.get_messages()[0]
            thread_id = first_message.get_thread_id()
            self.logger.info(f"Processing thread: {thread_id}")

            for message in messages:
                self.logger.info(
                    f"  Message from {message.get_user_name()} ({message.get_user_id()}) "
                    f"at {message.get_message_date()}: {message.get_message_content()}"
                )

        self.logger.info("DummyMessageConsumer finished processing messages")
