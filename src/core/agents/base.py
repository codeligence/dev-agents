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


"""Base agent implementations for common patterns."""

from abc import abstractmethod
from typing import Any, cast

from pydantic_ai import Agent as PydanticAgent
from pydantic_ai import RunContext

from core.exceptions import AgentGracefulExit
from core.log import get_logger
from core.protocols.agent_protocols import Agent, AgentExecutionContext


class PydanticAIAgent(Agent):
    """Abstract base class for agents that use PydanticAI.

    Provides common implementation patterns for agents that:
    - Use PydanticAI for LLM interactions
    - Process message history from context
    - Follow standard execution flow

    Maintains protocol compatibility while reducing code duplication.
    """

    def __init__(self, context: AgentExecutionContext) -> None:
        """Initialize the agent with execution context.

        Args:
            context: Execution context providing access to messages, config, and communication
        """
        self.context = context
        self.result: str | None = None
        self.logger = get_logger(self.__class__.__name__)

        # Subclasses must set up self.agent (PydanticAgent instance)
        self.agent: PydanticAgent[Any, Any] | None = None

    @abstractmethod
    def setup_agent(self) -> None:
        """Set up the PydanticAI agent instance.

        Subclasses must implement this to configure self.agent with:
        - Model configuration
        - System prompts
        - Result type
        - Any tools or other settings
        """
        ...

    def get_dependencies(self) -> Any:
        """Get dependencies for the PydanticAI agent.

        Returns:
            Dependencies object for agents that use deps_type, None otherwise
        """
        return None

    async def send_toolcall_message(
        self, ctx: RunContext[Any], fallback_message: str | None = None
    ) -> None:
        """
        Some models provide a message for the user when calling tools. Use it to inform the user.

        Args:
            ctx: PydanticAI RunContext containing the conversation messages
            fallback_message: Optional fallback message to send if no text part is found
        """
        if not ctx.messages:
            return

        last_model_response = ctx.messages[-1]
        text_part = next(
            (part for part in last_model_response.parts if part.part_kind == "text"),
            None,
        )
        if text_part:
            response_text = text_part.content
            await self.context.send_status(response_text)
        elif fallback_message:
            await self.context.send_status(fallback_message)

    async def run(self) -> str:
        """Execute the agent using standard PydanticAI flow.

        Template method that handles:
        - Message validation and processing
        - Status reporting
        - PydanticAI execution
        - Response delivery
        - Error handling

        Returns:
            AI-generated response string
        """
        # Ensure agent is set up
        if self.agent is None:
            self.setup_agent()

        if self.agent is None:
            raise RuntimeError(
                "setup_agent() must set self.agent to a PydanticAgent instance"
            )

        self.logger.info(f"Starting {self.__class__.__name__} execution")

        try:
            # Get messages from context
            message_list = self.context.get_message_list()

            if not message_list:
                self.logger.warning("No messages to respond to")
                response = (
                    "I don't see any messages to respond to. Please send me a message!"
                )
                await self.context.send_response(response)
                return response

            # Get chat history for processing
            chat_history = message_list.to_pydantic_chat_history()
            self.logger.info(
                f"Processing conversation with {len(chat_history)} message groups"
            )

            # Use PydanticAI to generate response with full chat history
            self.logger.info("Calling PydanticAI agent with chat history...")

            # Get dependencies if the agent uses them
            deps = self.get_dependencies()
            if deps is not None:
                result = await self.agent.run(message_history=chat_history, deps=deps)
            else:
                result = await self.agent.run(message_history=chat_history)

            response = result.output

            self.logger.info(
                f"Generated response: {response[:100]}..."
                if len(response) > 100
                else f"Generated response: {response}"
            )
            await self.context.send_response(response)

            self.result = response
            return cast("str", response)

        except AgentGracefulExit:
            # Re-raise without interception - let it propagate up naturally
            raise

        except Exception as e:
            error_msg = f"Error in {self.__class__.__name__}: {str(e)}"
            self.logger.error(error_msg)
            await self.context.send_response(f"Sorry, I encountered an error: {str(e)}")
            raise
