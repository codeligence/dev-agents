"""Tests for PydanticAI message history trimming utilities."""

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

from core.utils.message_utils import trim_trailing_tool_calls


def _user_request(content: str = "hello") -> ModelRequest:
    return ModelRequest(parts=[UserPromptPart(content=content)])


def _text_response(content: str = "hi") -> ModelResponse:
    return ModelResponse(parts=[TextPart(content=content)])


def _tool_call_response(tool_name: str = "search") -> ModelResponse:
    return ModelResponse(
        parts=[ToolCallPart(tool_name=tool_name, args={}, tool_call_id="call-1")]
    )


def _tool_return_request(tool_name: str = "search") -> ModelRequest:
    return ModelRequest(
        parts=[
            ToolReturnPart(tool_name=tool_name, content="result", tool_call_id="call-1")
        ]
    )


class TestTrimTrailingToolCalls:
    """Test cases for trim_trailing_tool_calls."""

    def test_none_input_returns_none(self):
        assert trim_trailing_tool_calls(None) is None

    def test_empty_input_returns_none(self):
        assert trim_trailing_tool_calls([]) is None

    def test_complete_history_is_unchanged(self):
        messages = [_user_request(), _text_response()]

        result = trim_trailing_tool_calls(messages)

        assert result == messages

    def test_trailing_tool_call_response_is_trimmed(self):
        messages = [_user_request(), _text_response(), _tool_call_response()]

        result = trim_trailing_tool_calls(messages)

        assert result == messages[:2]

    def test_input_list_is_not_mutated(self):
        messages = [_user_request(), _tool_call_response()]

        trim_trailing_tool_calls(messages)

        assert len(messages) == 2

    def test_trailing_interrupted_request_is_trimmed(self):
        """An aborted run leaves a partially assembled request behind."""
        interrupted = _tool_return_request()
        interrupted.state = "interrupted"
        messages = [_user_request(), _text_response(), interrupted]

        result = trim_trailing_tool_calls(messages)

        assert result == messages[:2]

    def test_trailing_interrupted_response_is_trimmed(self):
        interrupted = _text_response("partial")
        interrupted.state = "interrupted"
        messages = [_user_request(), _text_response(), interrupted]

        result = trim_trailing_tool_calls(messages)

        assert result == messages[:2]

    def test_trailing_incomplete_response_is_trimmed(self):
        incomplete = _text_response("still streaming")
        incomplete.state = "incomplete"
        messages = [_user_request(), _text_response(), incomplete]

        result = trim_trailing_tool_calls(messages)

        assert result == messages[:2]

    def test_interrupted_request_and_its_tool_call_are_both_trimmed(self):
        """Trimming cascades: dropping the partial request exposes the tool call."""
        interrupted = _tool_return_request()
        interrupted.state = "interrupted"
        messages = [
            _user_request(),
            _text_response(),
            _tool_call_response(),
            interrupted,
        ]

        result = trim_trailing_tool_calls(messages)

        assert result == messages[:2]

    def test_everything_trimmed_returns_none(self):
        interrupted = _tool_return_request()
        interrupted.state = "interrupted"

        assert trim_trailing_tool_calls([_tool_call_response(), interrupted]) is None

    def test_leading_interrupted_message_is_kept(self):
        """Only trailing partial messages are dropped."""
        interrupted = _text_response("partial")
        interrupted.state = "interrupted"
        messages = [_user_request(), interrupted, _user_request(), _text_response()]

        result = trim_trailing_tool_calls(messages)

        assert result == messages
