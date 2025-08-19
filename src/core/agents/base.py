"""Base agent implementations for common patterns."""

from abc import abstractmethod
from typing import Optional
from pydantic_ai import Agent as PydanticAgent, RunContext

from core.exceptions import AgentGracefulExit
from core.protocols.agent_protocols import Agent, AgentExecutionContext
from core.log import get_logger


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
        self.result: Optional[str] = None
        self.logger = get_logger(self.__class__.__name__)

        # Subclasses must set up self.agent (PydanticAgent instance)
        self.agent: Optional[PydanticAgent] = None

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

    def get_dependencies(self):
        """Get dependencies for the PydanticAI agent.

        Returns:
            Dependencies object for agents that use deps_type, None otherwise
        """
        return None

    async def send_toolcall_message(self, ctx: RunContext, fallback_message: Optional[str] = None) -> None:
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

    async def run(self):
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
            raise RuntimeError("setup_agent() must set self.agent to a PydanticAgent instance")

        self.logger.info(f"Starting {self.__class__.__name__} execution")

        try:
            # Get messages from context
            message_list = self.context.get_message_list()

            if not message_list:
                self.logger.warning("No messages to respond to")
                await self.context.send_response("I don't see any messages to respond to. Please send me a message!")
                return

            # Get chat history for processing
            chat_history = message_list.to_pydantic_chat_history()
            self.logger.info(f"Processing conversation with {len(chat_history)} message groups")

            # Use PydanticAI to generate response with full chat history
            self.logger.info("Calling PydanticAI agent with chat history...")

            # Get dependencies if the agent uses them
            deps = self.get_dependencies()
            if deps is not None:
                result = await self.agent.run(message_history=chat_history, deps=deps)
            else:
                result = await self.agent.run(message_history=chat_history)

            response = result.output

            self.logger.info(f"Generated response: {response[:100]}..." if len(response) > 100 else f"Generated response: {response}")
            await self.context.send_response(response)

            self.result = response
            return response

        except AgentGracefulExit:
            # Re-raise without interception - let it propagate up naturally
            raise

        except Exception as e:
            error_msg = f"Error in {self.__class__.__name__}: {str(e)}"
            self.logger.error(error_msg)
            await self.context.send_response(f"Sorry, I encountered an error: {str(e)}")
            raise
