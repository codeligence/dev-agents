"""Tests for safe agent runner with graceful error recovery."""

from pydantic_ai import Agent
from pydantic_ai.exceptions import AgentRunError, ModelHTTPError, UsageLimitExceeded
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import UsageLimits
import pytest

from core.agents.safe_runner import run_agent_safely

pytestmark = pytest.mark.anyio


class TestRunAgentSafely:
    """Test cases for run_agent_safely function."""

    async def test_successful_run_returns_normally(self):
        """Test that a successful run returns without triggering conclusion."""
        call_count = 0

        def mock_response(
            _messages: list[ModelMessage], _info: AgentInfo
        ) -> ModelResponse:
            nonlocal call_count
            call_count += 1
            return ModelResponse(parts=[TextPart(content="Success response")])

        model = FunctionModel(mock_response)
        agent = Agent(model)

        result = await run_agent_safely(agent, "test prompt")

        assert result.output == "Success response"
        assert call_count == 1  # Only one call, no conclusion needed

    async def test_usage_limit_exceeded_triggers_conclusion(self):
        """Test that UsageLimitExceeded is caught and conclusion run executes."""
        call_count = 0

        def mock_response(
            _messages: list[ModelMessage], _info: AgentInfo
        ) -> ModelResponse:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise UsageLimitExceeded("Token limit exceeded")
            return ModelResponse(parts=[TextPart(content="Conclusion response")])

        model = FunctionModel(mock_response)
        agent = Agent(model)

        result = await run_agent_safely(agent, "test prompt")

        assert result.output == "Conclusion response"
        assert call_count == 2  # First call failed, second (conclusion) succeeded

    async def test_model_http_error_triggers_conclusion(self):
        """Test that ModelHTTPError is caught and conclusion run executes."""
        call_count = 0

        def mock_response(
            _messages: list[ModelMessage], _info: AgentInfo
        ) -> ModelResponse:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ModelHTTPError(status_code=500, model_name="test")
            return ModelResponse(parts=[TextPart(content="Recovered")])

        model = FunctionModel(mock_response)
        agent = Agent(model)

        result = await run_agent_safely(agent, "test prompt")

        assert result.output == "Recovered"
        assert call_count == 2

    async def test_generic_agent_run_error_triggers_conclusion(self):
        """Test that generic AgentRunError is caught and conclusion run executes."""
        call_count = 0

        def mock_response(
            _messages: list[ModelMessage], _info: AgentInfo
        ) -> ModelResponse:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise AgentRunError("Generic error")
            return ModelResponse(parts=[TextPart(content="Recovered")])

        model = FunctionModel(mock_response)
        agent = Agent(model)

        result = await run_agent_safely(agent, "test prompt")

        assert result.output == "Recovered"
        assert call_count == 2

    async def test_conclusion_receives_captured_messages(self):
        """Test that conclusion run receives the captured message history."""
        received_messages: list[list[ModelMessage]] = []

        def mock_response(
            messages: list[ModelMessage], _info: AgentInfo
        ) -> ModelResponse:
            received_messages.append(list(messages))
            if len(received_messages) == 1:
                raise UsageLimitExceeded("Limit exceeded")
            return ModelResponse(parts=[TextPart(content="Done")])

        model = FunctionModel(mock_response)
        agent = Agent(model)

        await run_agent_safely(agent, "initial prompt")

        # Second call (conclusion) should have received messages from first call
        assert len(received_messages) == 2
        # Conclusion run should have more messages (includes the failed run's messages)
        assert len(received_messages[1]) >= len(received_messages[0])

    async def test_custom_conclude_message(self):
        """Test that custom conclude_message is used."""
        received_prompts: list[str] = []
        call_count = 0

        def mock_response(
            messages: list[ModelMessage], _info: AgentInfo
        ) -> ModelResponse:
            nonlocal call_count
            call_count += 1
            # Extract user prompt from messages
            for msg in messages:
                if hasattr(msg, "parts"):
                    for part in msg.parts:
                        if hasattr(part, "content") and isinstance(part.content, str):
                            received_prompts.append(part.content)
            if call_count == 1:
                raise UsageLimitExceeded("Limit exceeded")
            return ModelResponse(parts=[TextPart(content="Done")])

        model = FunctionModel(mock_response)
        agent = Agent(model)

        custom_message = "Please wrap up now"
        await run_agent_safely(
            agent,
            "test prompt",
            conclude_message=custom_message,
        )

        assert custom_message in received_prompts

    async def test_conclusion_has_no_usage_limits(self):
        """Test that conclusion run is called without usage limits."""
        # This is verified by the conclusion run succeeding even after
        # UsageLimitExceeded - if limits were passed, it might fail again
        call_count = 0

        def mock_response(
            _messages: list[ModelMessage], _info: AgentInfo
        ) -> ModelResponse:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise UsageLimitExceeded("Limit exceeded")
            return ModelResponse(parts=[TextPart(content="Success")])

        model = FunctionModel(mock_response)
        agent = Agent(model)

        # Even with strict limits, conclusion should succeed
        result = await run_agent_safely(
            agent,
            "test",
            usage_limits=UsageLimits(request_limit=1),
        )

        assert result.output == "Success"
        assert call_count == 2

    async def test_non_agent_run_error_propagates(self):
        """Test that non-AgentRunError exceptions are not caught."""

        def mock_response(
            _messages: list[ModelMessage], _info: AgentInfo
        ) -> ModelResponse:
            raise ValueError("Not an AgentRunError")

        model = FunctionModel(mock_response)
        agent = Agent(model)

        with pytest.raises(ValueError, match="Not an AgentRunError"):
            await run_agent_safely(agent, "test prompt")
