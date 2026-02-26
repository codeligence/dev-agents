"""Safe agent runner with graceful error recovery."""

from collections.abc import Sequence
from typing import Any, TypeVar

from pydantic_ai import Agent, RunUsage, capture_run_messages
from pydantic_ai.exceptions import AgentRunError
from pydantic_ai.messages import ModelMessage
from pydantic_ai.run import AgentRunResult
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import UsageLimits

from core.log import get_logger
from core.utils.message_utils import trim_trailing_tool_calls

logger = get_logger(__name__)

DepsT = TypeVar("DepsT")
OutputT = TypeVar("OutputT")

DEFAULT_CONCLUDE_MESSAGE = (
    "You have reached execution limits, please come to a conclusion now"
)


def _create_conclusion_agent(
    agent: Agent[DepsT, OutputT],
) -> Agent[DepsT, OutputT]:
    """Create a toolless agent for conclusion runs.

    Copies core configuration from the original agent but omits all tools,
    ensuring the conclusion run cannot invoke any tools.

    Args:
        agent: The original agent to copy configuration from

    Returns:
        A new agent with the same configuration but no tools
    """
    return Agent(
        model=agent.model,
        output_type=agent.output_type,
        instructions=agent._instructions,
        deps_type=agent.deps_type,
        model_settings=agent.model_settings,
        defer_model_check=True,  # Skip model validation since original was valid
    )


async def run_agent_safely(
    agent: Agent[DepsT, OutputT],
    user_prompt: str | Sequence[Any] | None = None,
    *,
    deps: DepsT = None,  # type: ignore[assignment]
    message_history: list[ModelMessage] | None = None,
    model_settings: ModelSettings | None = None,
    usage: RunUsage | None = None,
    usage_limits: UsageLimits | None = None,
    conclude_message: str = DEFAULT_CONCLUDE_MESSAGE,
) -> AgentRunResult[OutputT]:
    """Run an agent with graceful error recovery.

    When AgentRunError is raised (UsageLimitExceeded, ModelHTTPError,
    UnexpectedModelBehavior), catches the exception and runs a conclusion
    attempt with the FULL captured message history.

    How it works:
    1. capture_run_messages() creates a shared list for message history
    2. During agent.run(), all messages are appended to this shared list
    3. On exception, the list contains all successfully processed messages
    4. The conclusion run uses this captured history as its message_history

    Args:
        agent: The pydantic_ai Agent to run
        user_prompt: Initial user prompt
        deps: Agent dependencies
        message_history: Optional existing message history to continue from
        model_settings: Optional model settings
        usage_limits: Optional usage limits for the initial run
        conclude_message: Message to send for conclusion attempt

    Returns:
        AgentRunResult from either successful run or conclusion attempt
    """
    usage = usage or RunUsage()
    with capture_run_messages() as captured_messages:
        try:
            return await agent.run(
                user_prompt,
                deps=deps,
                message_history=message_history,
                model_settings=model_settings,
                usage=usage,
                usage_limits=usage_limits,
            )
        except AgentRunError as e:
            logger.warning(
                f"Agent run error ({type(e).__name__}): {e}, "
                f"attempting conclusion run with {len(captured_messages)} captured messages"
            )

            # captured_messages contains the FULL history:
            # - Original message_history that was passed in
            # - All request/response pairs from the failed run
            # - Only missing: the last response that caused the exception

            # Create toolless agent for conclusion to prevent further tool calls
            conclusion_agent = _create_conclusion_agent(agent)

            return await conclusion_agent.run(
                conclude_message,
                deps=deps,
                message_history=trim_trailing_tool_calls(captured_messages),
                model_settings=model_settings,
                usage=usage,
                usage_limits=UsageLimits(request_limit=None),  # Disable all limits
            )
