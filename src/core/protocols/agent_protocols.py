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


from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Protocol, Union

from pydantic_ai.usage import RunUsage

from core.config import BaseConfig
from core.message import MessageList
from core.prompts import BasePrompts

if TYPE_CHECKING:
    from pydantic_ai.models import Model

    from core.integrations.context_integration_loader import ContextIntegrationLoader
    from core.utils.progress_tracker import ProgressTracker


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

    def get_context_integration_loader(
        self, project_name: str = "default"
    ) -> "ContextIntegrationLoader":
        """Get a ContextIntegrationLoader for the specified project.

        Provides lazy initialization and caching of ContextIntegrationLoader instances.

        Args:
            project_name: Name of the project (defaults to "default")

        Returns:
            ContextIntegrationLoader instance for the project
        """
        from core.integrations.context_integration_loader import (
            ContextIntegrationLoader,
        )

        # Initialize cache if it doesn't exist
        if not hasattr(self, "_context_loaders"):
            object.__setattr__(self, "_context_loaders", {})

        context_loaders: dict[str, ContextIntegrationLoader] = getattr(
            self, "_context_loaders", {}
        )

        # Lazy load and cache the loader for this project
        if project_name not in context_loaders:
            project_config = self.get_config().get_project_config(project_name)
            context_loaders[project_name] = ContextIntegrationLoader(project_config)

        return context_loaders[project_name]

    def get_progress_tracker(self) -> "ProgressTracker":
        """Get a progress tracker configured with this context's status callback.

        Returns:
            ProgressTracker instance configured to report status via send_status()
        """
        from core.utils.progress_tracker import ProgressTracker

        return ProgressTracker(status_callback=self.send_status)

    def track_usage(
        self, model: Union[str, "Model"], usage: RunUsage | None = None
    ) -> None:
        """Track usage statistics for a model by incrementing existing totals.

        Accumulates usage statistics across multiple runs for the same model.
        Creates a new RunUsage instance if this is the first time tracking for the model.

        Args:
            model: Name/identifier of the model (string) or Model instance
            usage: RunUsage instance containing new usage statistics to add
        """
        if not usage or not model:
            return

        # Convert model to string if it's a Model instance
        model_name = model.model_name if hasattr(model, "model_name") else str(model)

        # Initialize cache if it doesn't exist
        if not hasattr(self, "_run_usage_by_model"):
            object.__setattr__(self, "_run_usage_by_model", {})

        run_usage_by_model: dict[str, RunUsage] = getattr(
            self, "_run_usage_by_model", {}
        )

        # Get existing usage or create new one
        if model_name not in run_usage_by_model:
            run_usage_by_model[model_name] = RunUsage()

        # Increment existing usage with new usage
        run_usage_by_model[model_name].incr(usage)

    def log_run_usages(self) -> None:
        """Log all RunUsage statistics accumulated during agent execution.

        Provides visibility into LLM usage across all models used in the current context.
        Should be called before context cleanup to capture final usage statistics.
        """
        if not hasattr(self, "_run_usage_by_model"):
            return

        run_usage_by_model: dict[str, RunUsage] = getattr(
            self, "_run_usage_by_model", {}
        )

        if not run_usage_by_model:
            return

        from core.log import get_logger

        logger = get_logger("RunUsage")

        logger.info("=== Agent Execution Usage Summary ===")
        for model, usage in run_usage_by_model.items():
            logger.info(
                f"Model: {model} | "
                f"Requests: {usage.requests} | "
                f"Input tokens: {usage.input_tokens} | "
                f"Output tokens: {usage.output_tokens} | "
                f"Total tokens: {usage.total_tokens}"
            )


class Agent(Protocol):
    """Protocol defining the interface for agents.

    Generic protocol that defines how agents should be implemented.
    Agents access execution context via context-local functions and execute via run() method.
    """

    def __init__(self) -> None:
        """Initialize the agent.

        Agents access execution context via context-local functions from core.agents.context
        rather than receiving it as a constructor parameter.
        """
        ...

    @abstractmethod
    async def run(self) -> Any:
        """Execute the agent."""
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
