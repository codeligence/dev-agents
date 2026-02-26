from dataclasses import dataclass, field
import logging

from core.log import get_logger
from entrypoints.slack_entrypoint.thread_task_manager import ThreadTaskManager
from integrations.slack.slack_client_service import SlackClientService


@dataclass
class StopCommandHandler:
    """Handles stop command detection and task cancellation."""

    slack_service: SlackClientService
    task_manager: ThreadTaskManager
    _logger: logging.Logger = field(
        default_factory=lambda: get_logger("StopCommandHandler")
    )

    def is_stop_command(self, content: str, thread_id: str, message_id: str) -> bool:
        """Check if message is a stop command (@bot stop).

        Args:
            content: The message content to check.
            thread_id: The thread identifier (parent ts for replies, own ts for top-level).
            message_id: The message's own timestamp.

        Returns:
            True if this is a stop command, False otherwise.
        """
        is_stop = (
            len(content) <= 25
            and self.slack_service.is_bot_mentioned(content)
            and "stop" in content.lower()
        )

        if is_stop and thread_id == message_id:
            self._logger.warning(
                "Stop command sent as top-level message (thread_id == message_id). "
                "To stop processing, reply with '@bot stop' in the same thread."
            )

        return is_stop

    def handle_stop(self, channel_id: str, thread_id: str) -> bool:
        """Handle stop command by cancelling the task and notifying the user.

        Args:
            channel_id: The Slack channel identifier.
            thread_id: The Slack thread identifier.

        Returns:
            True if task was cancelled, False otherwise.
        """
        if self.task_manager.cancel_task(thread_id):
            self.slack_service.send_reply(
                channel_id, thread_id, "Ok, processing stopped."
            )
            self._logger.info(f"Stopped processing for thread {thread_id}")
            return True
        return False
