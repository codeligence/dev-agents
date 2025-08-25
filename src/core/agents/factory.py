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


"""Agent factory for creating and configuring agents."""

from typing import Dict

from core.exceptions import AgentNotFoundError, AgentConfigurationError
from core.log import get_logger
from core.protocols.agent_protocols import Agent

logger = get_logger("AgentFactory")


class SimpleAgentFactory:
    """Simple factory implementation for creating agents.

    Maintains a registry of agent types and their factory functions.
    Follows the Factory pattern for centralized agent creation.
    """

    def __init__(self):
        self._agent_registry: Dict[str, callable] = {}

    def register_agent(self, agent_type: str, factory_func: callable) -> None:
        """Register an agent factory function.

        Args:
            agent_type: Unique identifier for the agent type
            factory_func: Function that creates and configures the agent
        """
        if agent_type in self._agent_registry:
            logger.warning(f"Overriding existing agent registration: {agent_type}")

        self._agent_registry[agent_type] = factory_func
        logger.info(f"Registered agent type: {agent_type}")

    def create_agent(self, agent_type: str) -> type[Agent]:
        """Create an agent class of the specified type.

        Args:
            agent_type: Type identifier for the agent to create

        Returns:
            Agent class that can be instantiated with context

        Raises:
            AgentNotFoundError: If agent type is not registered
            AgentConfigurationError: If agent creation fails
        """
        if agent_type not in self._agent_registry:
            available_types = list(self._agent_registry.keys())
            raise AgentNotFoundError(
                f"Agent type '{agent_type}' not found. Available types: {available_types}",
                agent_type
            )

        try:
            factory_func = self._agent_registry[agent_type]
            agent_class = factory_func()
            logger.info(f"Retrieved agent class: type={agent_type}")
            return agent_class

        except Exception as e:
            error_msg = f"Failed to get agent class of type '{agent_type}': {str(e)}"
            logger.error(error_msg)
            raise AgentConfigurationError(error_msg, agent_type) from e

    def get_registered_types(self) -> list[str]:
        """Get list of all registered agent types.

        Returns:
            List of registered agent type identifiers
        """
        return list(self._agent_registry.keys())