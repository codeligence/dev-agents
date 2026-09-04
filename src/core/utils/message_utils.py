"""Message utilities for PydanticAI message processing."""

from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart


def trim_trailing_tool_calls(
    messages: list[ModelMessage] | None,
) -> list[ModelMessage] | None:
    """Remove trailing messages that are not usable as message history.

    Two kinds of trailing messages are dropped, repeatedly, until the history
    ends on a clean message:

    - Messages whose lifecycle ``state`` is not ``'complete'``. PydanticAI marks
      partially assembled messages (``'interrupted'``, ``'incomplete'``,
      ``'suspended'``) when a run is aborted, and ``capture_run_messages()``
      exposes them so consumers can detect partial state.
    - ``ModelResponse`` messages containing a ``ToolCallPart``. When history is
      passed to a subagent from within a tool execution, it contains the current
      tool call which has no matching result yet.

    Args:
        messages: List of PydanticAI ModelMessage objects

    Returns:
        Messages with unusable trailing messages removed, or None if the input
        is None/empty or nothing usable remains
    """
    if not messages:
        return None

    result = list(messages)

    while result:
        last_msg = result[-1]

        if last_msg.state != "complete":
            result.pop()
            continue

        if isinstance(last_msg, ModelResponse) and any(
            isinstance(part, ToolCallPart) for part in last_msg.parts
        ):
            result.pop()
            continue

        break

    return result if result else None
