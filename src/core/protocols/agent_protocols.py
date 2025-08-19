from abc import abstractmethod
from typing import Protocol

from core.config import BaseConfig
from core.message import MessageList
from core.prompts import BasePrompts


class AgentExecutionContext(Protocol):
    """Protocol defining the execution context for agents.

    Provides standardized interface for agents to interact with their environment,
    report status, send responses, and access configuration and messages.
    """

    @abstractmethod
    async def send_status(self, message: str) -> None:
        """Report agent execution status to the user.

        Args:
            message: Status message to report
        """
        ...

    @abstractmethod
    async def send_response(self, response: str) -> None:
        """Send final response to the user.

        Args:
            response: Final response message
        """
        ...

    @abstractmethod
    def get_message_list(self) -> MessageList:
        """Get the list of messages available to the agent.

        Returns:
            MessageList containing available messages
        """
        ...

    @abstractmethod
    def get_config(self) -> BaseConfig:
        """Get the configuration object.

        Returns:
            BaseConfig instance for accessing configuration
        """
        ...

    @abstractmethod
    def get_prompts(self) -> BasePrompts:
        """Get the prompts object.

        Returns:
            BasePrompts instance for accessing prompts
        """
        ...

    @abstractmethod
    def get_execution_id(self) -> str:
        """Get the unique execution identifier for this agent context.

        Returns:
            Unique identifier that can be used for state persistence
        """
        ...


class Agent(Protocol):
    """Protocol defining the interface for agents.

    Generic protocol that defines how agents should be implemented.
    Agents receive context during initialization and execute via run() method.
    """

    def __init__(self, context: AgentExecutionContext) -> None:
        """Initialize the agent with execution context.

        Args:
            context: Execution context providing access to messages, config, and communication
        """
        ...

    @abstractmethod
    async def run(self):
        """Execute the agent.
        """
        ...


class AgentFactory(Protocol):
    """Protocol for agent factories.

    Defines interface for creating and configuring agents.
    """

    @abstractmethod
    def create_agent(self, agent_type: str) -> type[Agent]:
        """Create an agent class of the specified type.

        Args:
            agent_type: Type identifier for the agent to create

        Returns:
            Agent class that can be instantiated with context
        """
        ...
