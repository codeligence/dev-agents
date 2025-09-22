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


"""Slack implementation of AgentExecutionContext."""

from typing import Any
import contextlib
import uuid

from core.config import BaseConfig
from core.log import get_logger
from core.message import MessageList
from core.prompts import BasePrompts
from core.protocols.agent_protocols import AgentExecutionContext
from integrations.slack.slack_client_service import SlackClientService

logger = get_logger("SlackAgentContext")


class SlackAgentContext(AgentExecutionContext):
    """Slack-specific implementation of AgentExecutionContext.

    Provides Slack-specific message reporting and thread management
    while implementing the standard agent execution interface.
    """

    def __init__(
        self,
        slack_client: SlackClientService,
        channel_id: str,
        thread_ts: str | None,
        message_list: MessageList,
        config: BaseConfig,
        prompts: BasePrompts,
    ):
        self.slack_client = slack_client
        self.channel_id = channel_id
        self.thread_ts = thread_ts
        self.message_list = message_list
        self.config = config
        self.prompts = prompts
        self.context_id = str(uuid.uuid4())
        self.last_message_ts: str | None = None

        # Check if bot is mentioned in the last message
        self._bot_mentioned = False
        if message_list and len(message_list) > 0:
            messages = message_list.get_messages()
            if messages:
                last_message = messages[-1]
                self._bot_mentioned = slack_client.is_bot_mentioned(
                    last_message.get_message_content()
                )

        logger.info(
            f"Created Slack agent context: channel={channel_id}, thread={thread_ts}, context_id={self.context_id}, bot_mentioned={self._bot_mentioned}"
        )

    async def _send_or_update_message(
        self, text: str, is_status: bool = False
    ) -> str | None:
        """Send a new message or update the last message if it exists.

        Args:
            text: Message text to send
            is_status: Whether this is a status message - if True, stores timestamp for future updates;
                      if False, clears timestamp after sending (final response)

        Returns:
            Message timestamp if successful, None otherwise
        """
        try:
            if self.last_message_ts:
                # Update existing message
                logger.debug(f"Updating existing message {self.last_message_ts}")
                message_ts = self.slack_client.update_message(
                    thread_ts=self.thread_ts or self.channel_id,
                    message_ts=self.last_message_ts,
                    text=text,
                )
                action = "Updated"
            else:
                # Send new message
                logger.debug("Sending new message")
                message_ts = self.slack_client.send_reply(
                    thread_ts=self.thread_ts or self.channel_id, text=text
                )
                action = "Sent"

            if message_ts:
                msg_type = "status" if is_status else "response"
                logger.info(f"{action} {msg_type} message: {message_ts}")

                # Manage last_message_ts based on message type
                if is_status:
                    # Status messages - store timestamp for future updates
                    self.last_message_ts = message_ts
                else:
                    # Response messages - clear timestamp (final message)
                    self.last_message_ts = None

            return message_ts

        except Exception as e:
            logger.error(
                f"Failed to send/update message: {type(e).__name__}: {str(e)}",
                exc_info=True,
            )
            logger.error(
                f"Context: channel_id={self.channel_id}, thread_ts={self.thread_ts}, last_message_ts={self.last_message_ts}"
            )
            return None

    async def send_status(self, message: str) -> None:
        """Send agent execution status to Slack.

        Posts a status message to the Slack channel/thread.

        Args:
            message: Status message to send
        """
        logger.info(f"Sending status: {message}")

        # Format status message with emoji for better UX
        formatted_message = f"{message}"

        # Send or update message - timestamp management handled by shared method
        await self._send_or_update_message(formatted_message, is_status=True)

    async def send_response(self, response: str) -> None:
        """Send final response to Slack.

        Posts the agent's final response to the Slack channel/thread.

        Args:
            response: Final response message
        """
        logger.info(f"Sending response: {response[:100]}...")

        # Send or update message - timestamp cleared automatically by shared method
        message_ts = await self._send_or_update_message(response, is_status=False)

        if not message_ts:
            logger.error("Failed to send response to Slack - message_ts is None")
            # Try to send an error message
            with contextlib.suppress(Exception):
                await self._send_or_update_message(
                    "❌ Sorry, I encountered an error while sending my response.",
                    is_status=False,
                )
            raise Exception("Failed to send response to Slack: message_ts is None")

    def get_message_list(self) -> MessageList:
        """Get the list of messages available to the agent.

        Returns:
            MessageList containing available messages
        """
        return self.message_list

    def get_config(self) -> BaseConfig:
        """Get the configuration object.

        Returns:
            BaseConfig instance for accessing configuration
        """
        return self.config

    def get_prompts(self) -> BasePrompts:
        """Get the prompts object.

        Returns:
            BasePrompts instance for accessing prompts
        """
        return self.prompts

    def get_context_id(self) -> str:
        """Get the unique context identifier.

        Returns:
            Unique identifier for this execution context
        """
        return self.context_id

    def get_execution_id(self) -> str:
        """Get the unique execution identifier for this agent context.

        Uses thread_ts as the primary identifier for state persistence.
        Falls back to channel_id if no thread exists.

        Returns:
            Unique identifier that can be used for state persistence
        """
        return self.thread_ts or self.channel_id

    def get_slack_info(self) -> dict[str, Any]:
        """Get Slack-specific context information.

        Returns:
            Dictionary containing Slack channel and thread information
        """
        return {
            "channel_id": self.channel_id,
            "thread_ts": self.thread_ts,
            "context_id": self.context_id,
        }

    def is_bot_mentioned(self) -> bool:
        """Check if the bot was mentioned in the last message.

        Returns:
            True if the bot was mentioned in the last message, False otherwise
        """
        return self._bot_mentioned
