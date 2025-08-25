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


"""Core domain exceptions for the agent framework."""


class AgentException(Exception):
    """Base exception for all agent-related errors."""
    
    def __init__(self, message: str, agent_type: str = None):
        super().__init__(message)
        self.agent_type = agent_type


class AgentExecutionError(AgentException):
    """Raised when an agent fails during execution."""
    pass


class AgentConfigurationError(AgentException):
    """Raised when agent configuration is invalid or missing."""
    pass


class AgentNotFoundError(AgentException):
    """Raised when requested agent type is not found."""
    pass


class AgentContextError(AgentException):
    """Raised when there are issues with the execution context."""
    pass


class AgentTimeoutError(AgentException):
    """Raised when agent execution exceeds timeout limits."""
    pass


class AgentGracefulExit(AgentException):
    """Raised by agents to gracefully terminate processing without error."""
    pass


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""
    pass