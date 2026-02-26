"""Plain Subagent for structured output with optional dependencies.

This subagent provides a simple PydanticAI agent for generating structured
output. Supports optional dependencies for conversational agents.
"""

from typing import Any, TypeVar

from pydantic_ai import Agent as PydanticAgent

# Type variable for dependencies
DepsT = TypeVar("DepsT")


def create_plain_subagent(
    model: str,
    system_prompt: str,
    num_retries: int = 3,
    output_type: type[Any] = str,
    deps_type: type[DepsT] | None = None,
) -> PydanticAgent[DepsT, Any] | PydanticAgent[None, Any]:
    """Create a plain agent for structured output with optional dependencies.

    Args:
        model: LLM model to use (e.g., 'openai:gpt-4o-mini')
        system_prompt: System prompt for the agent
        num_retries: Number of retries for failed requests (default: 3)
        output_type: Return type for the agent (default: str)
        deps_type: Optional dependencies type for the agent

    Returns:
        Configured PydanticAI agent, with or without dependencies support
    """
    if deps_type is not None:
        agent: PydanticAgent[DepsT, Any] = PydanticAgent(
            model=model,
            deps_type=deps_type,
            output_type=output_type,
            instructions=system_prompt,
            retries=num_retries,
        )
        return agent
    else:
        agent_no_deps: PydanticAgent[None, Any] = PydanticAgent(
            model=model,
            output_type=output_type,
            instructions=system_prompt,
            retries=num_retries,
        )
        return agent_no_deps
