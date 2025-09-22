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


"""Agent orchestration service for managing agent execution."""

from collections.abc import Callable
from typing import cast
import asyncio
import time
import uuid

from core.agents.context import (
    has_agent_execution_context,
    reset_agent_execution_context,
    set_agent_execution_context,
)
from core.agents.factory import SimpleAgentFactory
from core.exceptions import AgentExecutionError, AgentGracefulExit, AgentTimeoutError
from core.log import get_logger
from core.protocols.agent_protocols import Agent, AgentExecutionContext

logger = get_logger("AgentService")


class AgentService:
    """Service for orchestrating agent execution with proper error handling and monitoring."""

    def __init__(self, default_timeout_seconds: int = 6000):
        self.default_timeout_seconds = default_timeout_seconds
        self.agent_factory = SimpleAgentFactory()

    def register_agent(
        self, agent_type: str, factory_func: Callable[[], type[Agent]]
    ) -> None:
        """Register an agent factory function.

        Args:
            agent_type: Unique identifier for the agent type
            factory_func: Function that creates and configures the agent
        """
        self.agent_factory.register_agent(agent_type, factory_func)
        logger.info(f"Agent registered with service: {agent_type}")

    def get_registered_agent_types(self) -> list[str]:
        """Get list of all registered agent types."""
        return self.agent_factory.get_registered_types()

    async def execute_agent_by_type(
        self,
        agent_type: str,
        context: AgentExecutionContext,
        timeout_seconds: int | None = None,
    ) -> str:
        """Create and execute an agent by type.

        Args:
            agent_type: Type identifier for the agent to create and execute
            context: Execution context for the agent
            timeout_seconds: Optional timeout override

        Returns:
            Result from agent execution

        Raises:
            AgentNotFoundError: If agent type is not registered
            AgentExecutionError: If agent execution fails
            AgentTimeoutError: If agent execution exceeds timeout
        """
        logger.info(f"Creating and executing agent by type: {agent_type}")

        # Get agent class from factory
        agent_class = self.agent_factory.create_agent(agent_type)

        return await self.execute_agent_class(
            agent_class, context, agent_type, timeout_seconds
        )

    async def execute_agent_class(
        self,
        agent_class: type[Agent],
        context: AgentExecutionContext,
        agent_type: str = "unknown",
        timeout_seconds: int | None = None,
    ) -> str:
        """Execute an agent class by first setting context, then creating the agent.

        Args:
            agent_class: The agent class to instantiate and execute
            context: Execution context for the agent
            agent_type: Type identifier for the agent (for logging/monitoring)
            timeout_seconds: Optional timeout override

        Returns:
            Result from agent execution

        Raises:
            AgentExecutionError: If agent execution fails
            AgentTimeoutError: If agent execution exceeds timeout
        """
        # Set agent execution context BEFORE creating the agent
        context_token = set_agent_execution_context(context)

        try:
            # Create agent after context is set
            agent = agent_class()

            # Use existing execute_agent method for full error handling
            return await self.execute_agent(agent, context, agent_type, timeout_seconds)

        finally:
            # Always reset context
            reset_agent_execution_context(context_token)

    async def execute_agent(
        self,
        agent: Agent,
        context: AgentExecutionContext,
        agent_type: str = "unknown",
        timeout_seconds: int | None = None,
    ) -> str:
        """Execute an agent with proper orchestration, monitoring, and error handling.

        Args:
            agent: The agent to execute
            context: Execution context for the agent
            agent_type: Type identifier for the agent (for logging/monitoring)
            timeout_seconds: Optional timeout override

        Returns:
            Result from agent execution

        Raises:
            AgentExecutionError: If agent execution fails
            AgentTimeoutError: If agent execution exceeds timeout
        """
        execution_id = str(uuid.uuid4())
        timeout = timeout_seconds or self.default_timeout_seconds
        start_time = time.time()

        logger.info(
            f"Starting agent execution: type={agent_type}, execution_id={execution_id}"
        )

        # Set agent execution context for the duration of agent execution (if not already set)
        context_already_set = has_agent_execution_context()
        context_token = (
            None if context_already_set else set_agent_execution_context(context)
        )

        try:
            # Execute agent with timeout - agents access context via context-local functions
            result = await asyncio.wait_for(agent.run(), timeout=timeout)

            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"Agent execution completed: type={agent_type}, time={execution_time_ms}ms"
            )
            return cast("str", result)

        except TimeoutError:
            execution_time_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Agent execution timed out after {timeout} seconds"
            logger.error(
                f"Agent timeout: type={agent_type}, time={execution_time_ms}ms"
            )

            await context.send_status(
                f"Agent execution timed out after {timeout} seconds"
            )
            raise AgentTimeoutError(error_msg, agent_type)

        except AgentGracefulExit:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"Agent graceful exit: type={agent_type}, time={execution_time_ms}ms"
            )
            # Silently finish - no error raised, no status sent
            return "Agent completed gracefully"

        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            error_msg = f"Agent execution failed: {str(e)}"
            logger.error(
                f"Agent execution error: type={agent_type}, error={error_msg}, time={execution_time_ms}ms"
            )

            await context.send_status(f"Agent execution failed: {str(e)}")
            raise AgentExecutionError(error_msg, agent_type) from e

        finally:
            # Log usage statistics before context cleanup
            context.log_run_usages()
            # Reset the context only if we set it
            if context_token is not None:
                reset_agent_execution_context(context_token)
