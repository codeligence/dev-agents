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


from collections.abc import Callable
from typing import TYPE_CHECKING

from pydantic_ai import Agent
from pydantic_ai.usage import RunUsage

from core.log import get_logger

if TYPE_CHECKING:
    from core.protocols.agent_protocols import AgentExecutionContext

# Module-level variables for optional context access
_has_context_function = False
get_current_agent_execution_context: (
    Callable[[], "AgentExecutionContext | None"] | None
) = None


# Try to import the context function at module level
try:
    from core.agents.context import get_current_agent_execution_context

    _has_context_function = True
except ImportError:
    pass

logger = get_logger(logger_name="LLM", level="DEBUG")


def _create_agent(model_full_name: str) -> Agent[None, str]:
    return Agent(
        model=model_full_name,
        output_type=str,
    )


def _track_usage_for_model(model_full_name: str, usage: RunUsage | None) -> None:
    """Track RunUsage for a model if running within agent context."""
    if not (_has_context_function and get_current_agent_execution_context):
        return

    try:
        context = get_current_agent_execution_context()
        if context:
            context.track_usage(model_full_name, usage)
    except (RuntimeError, AttributeError):
        # If we can't get the context, continue without usage tracking
        pass


def invoke_llm(prompt_text: str, model_full_name: str) -> str:
    logger.info(
        f"Invoking LLM with model={model_full_name}, prompt_text[:200]={prompt_text[:200]!r}"
    )
    agent = _create_agent(model_full_name)
    result = agent.run_sync(prompt_text)

    # Track usage after execution
    _track_usage_for_model(model_full_name, result.usage())

    return result.output


async def invoke_llm_async(prompt_text: str, model_full_name: str) -> str:
    logger.info(
        f"Invoking LLM async with model={model_full_name}, prompt_text[:200]={prompt_text[:200]!r}"
    )
    agent = _create_agent(model_full_name)
    result = await agent.run(prompt_text)

    # Track usage after execution
    _track_usage_for_model(model_full_name, result.usage())

    return result.output
