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

    def __init__(self):
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
