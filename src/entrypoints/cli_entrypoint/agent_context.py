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


"""CLI implementation of AgentExecutionContext."""

from datetime import datetime
import sys
import uuid

from core.config import BaseConfig
from core.log import get_logger
from core.message import MessageList
from core.prompts import BasePrompts
from core.protocols.agent_protocols import AgentExecutionContext
from entrypoints.cli_entrypoint.message import CLIMessage

logger = get_logger("CLIAgentContext")


def _supports_color() -> bool:
    """Check if terminal supports ANSI colors."""
    return (
        hasattr(sys.stdout, "isatty")
        and sys.stdout.isatty()
        and hasattr(sys.stderr, "isatty")
        and sys.stderr.isatty()
    )


def _colorize(text: str, color_code: str) -> str:
    """Add ANSI color codes to text if terminal supports colors."""
    if _supports_color():
        return f"\033[{color_code}m{text}\033[0m"
    return text


def _red(text: str) -> str:
    """Make text red if terminal supports colors."""
    return _colorize(text, "31;1")  # Bold bright red


def _green(text: str) -> str:
    """Make text green if terminal supports colors."""
    return _colorize(text, "92")  # Bright green


class CLIAgentContext(AgentExecutionContext):
    """CLI specific implementation of AgentExecutionContext.

    Provides console-based interaction where:
    - send_status() prints status messages (not stored in history)
    - send_response() prints response and adds to conversation history
    """

    def __init__(
        self,
        message_list: MessageList,
        config: BaseConfig,
        prompts: BasePrompts,
        thread_id: str = "cli-session",
    ):
        self.message_list = message_list
        self.config = config
        self.prompts = prompts
        self.thread_id = thread_id
        self.execution_id = str(uuid.uuid4())

        logger.info(
            f"Created CLI agent context: thread_id={thread_id}, execution_id={self.execution_id}"
        )

    async def send_status(self, message: str) -> None:
        """Send agent execution status by printing to console.

        Status messages are printed but NOT added to conversation history.

        Args:
            message: Status message to print
        """
        print(f"🔄 {message}")
        logger.info(f"Status: {message}")

    async def send_response(self, response: str) -> None:
        """Send final response by printing to console and adding to history.

        Response is both printed and added to the conversation history
        for future context.

        Args:
            response: Final response message
        """
        print(f"\n\n{_red(f'Assistant: {response}')}\n\n")
        logger.info(f"Response: {response[:100]}...")

        # Add response to message history
        response_message = CLIMessage(
            message_id=str(uuid.uuid4()),
            role="assistant",
            content=response,
            timestamp=datetime.now(),
            thread_id=self.thread_id,
        )

        self.message_list.add_message(response_message)

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

    def get_execution_id(self) -> str:
        """Get the unique execution identifier for this agent context.

        Returns:
            Unique identifier that can be used for state persistence
        """
        return self.execution_id

    def add_user_message(self, content: str) -> None:
        """Add a user message to the conversation history.

        Args:
            content: User's message content
        """
        user_message = CLIMessage(
            message_id=str(uuid.uuid4()),
            role="user",
            content=content,
            timestamp=datetime.now(),
            thread_id=self.thread_id,
        )

        self.message_list.add_message(user_message)
        logger.info(f"Added user message: {content[:50]}...")
