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


"""Agent execution context management using contextvars.

Provides thread-safe context management for agent execution environments.
Enables any code within an agent execution context to access context information
without explicit parameter passing.
"""

from typing import NoReturn
import contextvars

from core.config import BaseConfig
from core.prompts import BasePrompts
from core.protocols.agent_protocols import AgentExecutionContext

# Context variable to hold the current agent execution context
agent_execution_context_var: contextvars.ContextVar[AgentExecutionContext] = (
    contextvars.ContextVar("agent_execution_context")
)


def set_agent_execution_context(
    context: AgentExecutionContext,
) -> contextvars.Token[AgentExecutionContext]:
    """Set the current agent execution context.

    Args:
        context: The AgentExecutionContext to set

    Returns:
        Token that can be used to reset the context
    """
    return agent_execution_context_var.set(context)


def reset_agent_execution_context(
    token: contextvars.Token[AgentExecutionContext],
) -> None:
    """Reset the agent execution context using the provided token.

    Args:
        token: Token returned from set_agent_execution_context()
    """
    agent_execution_context_var.reset(token)


def get_current_agent_execution_context() -> AgentExecutionContext:
    """Get the current agent execution context.

    Returns:
        The current AgentExecutionContext

    Raises:
        LookupError: If no agent execution context is currently set
    """
    try:
        return agent_execution_context_var.get()
    except LookupError:
        _raise_no_context_error()


def has_agent_execution_context() -> bool:
    """Check if an agent execution context is currently set.

    Returns:
        True if context is set, False otherwise
    """
    try:
        agent_execution_context_var.get()
        return True
    except LookupError:
        return False


def _raise_no_context_error() -> NoReturn:
    """Raise a descriptive error when no context is available."""
    raise RuntimeError(
        "No agent execution context is currently set. "
        "This function can only be called from within an agent execution context."
    )


# Convenience functions for common context operations


def get_current_config() -> BaseConfig:
    """Get the current configuration from the agent execution context.

    Returns:
        BaseConfig instance

    Raises:
        RuntimeError: If no agent execution context is currently set
    """
    return get_current_agent_execution_context().get_config()


def get_current_prompts() -> BasePrompts:
    """Get the current prompts from the agent execution context.

    Returns:
        BasePrompts instance

    Raises:
        RuntimeError: If no agent execution context is currently set
    """
    return get_current_agent_execution_context().get_prompts()
