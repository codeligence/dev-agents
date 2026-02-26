"""Tests for AgentService hook integration."""

from unittest.mock import AsyncMock

import pytest

from core.agents.service import AgentService
from core.hooks import hooks
from core.protocols.agent_protocols import Agent, AgentExecutionContext


class TestAgentServiceCreatedHook:
    """Tests for the agent_service.created action hook."""

    @pytest.fixture(autouse=True)
    def _clear_hooks(self):
        """Clear hooks before and after each test for isolation."""
        hooks().clear()
        yield
        hooks().clear()

    def test_hook_fires_on_construction(self):
        """The agent_service.created hook fires when AgentService is created."""
        received: list[AgentService] = []
        hooks().add_action(
            "agent_service.created", lambda service: received.append(service)
        )

        service = AgentService()

        assert len(received) == 1
        assert received[0] is service

    def test_listener_can_register_agent_via_hook(self):
        """A hook listener can register agents on the service."""

        class DummyAgent(Agent):
            async def run(self) -> str:
                return "dummy"

        def register_agents(service: AgentService) -> None:
            service.register_agent("dummy_agent", lambda: DummyAgent)

        hooks().add_action("agent_service.created", register_agents)

        service = AgentService()

        assert "dummy_agent" in service.get_registered_agent_types()

    def test_multiple_listeners_execute_in_priority_order(self):
        """Multiple hook listeners execute in priority order."""
        order: list[str] = []

        def first(_service: AgentService) -> None:
            order.append("first")

        def second(_service: AgentService) -> None:
            order.append("second")

        hooks().add_action("agent_service.created", second, priority=20)
        hooks().add_action("agent_service.created", first, priority=5)

        AgentService()

        assert order == ["first", "second"]


class TestExecuteAgentNameFilter:
    """Tests for the agent_service.execute_agent_name filter hook."""

    @pytest.fixture(autouse=True)
    def _clear_hooks(self):
        """Clear hooks before and after each test for isolation."""
        hooks().clear()
        yield
        hooks().clear()

    @pytest.fixture()
    def mock_context(self) -> AgentExecutionContext:
        """Create a mock AgentExecutionContext."""
        ctx = AsyncMock(spec=AgentExecutionContext)
        ctx.log_run_usages = lambda: None
        return ctx

    @pytest.fixture()
    def service(self) -> AgentService:
        """Create an AgentService with test agents registered."""

        class AlphaAgent(Agent):
            async def run(self) -> str:
                return "alpha"

        class BetaAgent(Agent):
            async def run(self) -> str:
                return "beta"

        service = AgentService()
        service.register_agent("alpha", lambda: AlphaAgent)
        service.register_agent("beta", lambda: BetaAgent)
        return service

    async def test_filter_can_override_agent_name(
        self, service: AgentService, mock_context: AgentExecutionContext
    ):
        """A filter listener can redirect execution to a different agent."""
        hooks().add_filter("agent_service.execute_agent_name", lambda _name: "beta")

        result = await service.execute_agent_by_type("alpha", mock_context)

        assert result == "beta"

    async def test_no_filter_uses_original_name(
        self, service: AgentService, mock_context: AgentExecutionContext
    ):
        """Without filters, the original agent name is used."""
        result = await service.execute_agent_by_type("alpha", mock_context)

        assert result == "alpha"
