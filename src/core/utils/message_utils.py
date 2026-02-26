"""Message utilities for PydanticAI message processing."""

from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart


def trim_trailing_tool_calls(
    messages: list[ModelMessage] | None,
) -> list[ModelMessage] | None:
    """Remove trailing messages that contain tool calls without results.

    When passing message history to a subagent from within a tool execution,
    the history contains the current tool call which hasn't completed yet.
    This function trims those incomplete tool calls from the end.

    Args:
        messages: List of PydanticAI ModelMessage objects

    Returns:
        Messages with trailing tool call messages removed, or None if input is None/empty
    """
    if not messages:
        return None

    result = list(messages)

    # Trim trailing ModelResponse messages that contain ToolCallPart
    while result:
        last_msg = result[-1]
        if isinstance(last_msg, ModelResponse):
            has_tool_call = any(
                isinstance(part, ToolCallPart) for part in last_msg.parts
            )
            if has_tool_call:
                result.pop()
                continue
        break

    return result if result else None
