"""Tests for skills.scheduler.tools — PydanticAI tool registrations."""

from unittest.mock import MagicMock, patch
import inspect

import pytest

from core import context_factory
from skills.scheduler.tools import get_tool_registrations


@pytest.fixture
def clean_origin_registry():
    """Snapshot and restore the global origin-factory registry around a test.

    The registry is a module-level dict in core.context_factory; tests that
    register entries here must not leak into siblings.
    """
    snapshot = dict(context_factory._factories)
    context_factory._factories.clear()
    try:
        yield context_factory
    finally:
        context_factory._factories.clear()
        context_factory._factories.update(snapshot)


class TestGetToolRegistrations:
    def test_returns_three_tools(self):
        tools = get_tool_registrations()
        assert len(tools) == 3

    def test_tool_names(self):
        tools = get_tool_registrations()
        names = {t.name for t in tools}
        assert names == {"create_schedule", "list_schedules", "delete_schedule"}

    def test_tools_have_descriptions(self):
        tools = get_tool_registrations()
        for tool in tools:
            assert tool.description
            assert len(tool.description) > 10

    def test_tools_have_async_functions(self):
        tools = get_tool_registrations()

        for tool in tools:
            assert inspect.iscoroutinefunction(tool.function)

    def test_tools_have_ascending_priority(self):
        tools = get_tool_registrations()
        priorities = [t.priority for t in tools]
        assert priorities == sorted(priorities)


class TestCreateScheduleTool:
    @pytest.mark.asyncio
    async def test_create_success(self):
        tools = get_tool_registrations()
        create_tool = next(t for t in tools if t.name == "create_schedule")

        mock_ctx = MagicMock()

        with (
            patch("skills.scheduler.tools.SkillContext") as mock_sc_cls,
            patch(
                "skills.scheduler.tools.is_origin_factory_registered",
                return_value=True,
            ),
            patch("skills.scheduler.skill.create_schedule") as mock_create,
        ):
            mock_sc = MagicMock()
            mock_sc.execution_context.get_origin_info.return_value = {
                "type": "slack",
                "channel_id": "C123",
            }
            mock_sc_cls.return_value = mock_sc
            mock_create.return_value = {
                "id": "abc123",
                "cron": "0 9 * * 1",
                "task": "weekly report",
            }

            result = await create_tool.function(
                mock_ctx, cron="0 9 * * 1", task="weekly report"
            )

        assert "abc123" in result
        assert "0 9 * * 1" in result
        mock_create.assert_called_once_with(
            cron="0 9 * * 1",
            task="weekly report",
            origin_info={"type": "slack", "channel_id": "C123"},
        )

    @pytest.mark.asyncio
    async def test_create_invalid_cron(self):
        tools = get_tool_registrations()
        create_tool = next(t for t in tools if t.name == "create_schedule")

        mock_ctx = MagicMock()

        with (
            patch("skills.scheduler.tools.SkillContext") as mock_sc_cls,
            patch(
                "skills.scheduler.tools.is_origin_factory_registered",
                return_value=True,
            ),
            patch("skills.scheduler.skill.create_schedule") as mock_create,
        ):
            mock_sc = MagicMock()
            mock_sc.execution_context.get_origin_info.return_value = {"type": "slack"}
            mock_sc_cls.return_value = mock_sc
            mock_create.side_effect = ValueError("bad cron")

            result = await create_tool.function(mock_ctx, cron="bad", task="test")

        assert "Invalid cron" in result

    @pytest.mark.asyncio
    async def test_create_rejected_when_no_factory_registered(self):
        """Origin types without a registered factory must be refused up front."""
        tools = get_tool_registrations()
        create_tool = next(t for t in tools if t.name == "create_schedule")

        mock_ctx = MagicMock()

        with (
            patch("skills.scheduler.tools.SkillContext") as mock_sc_cls,
            patch(
                "skills.scheduler.tools.is_origin_factory_registered",
                return_value=False,
            ) as mock_registered,
            patch("skills.scheduler.skill.create_schedule") as mock_create,
        ):
            mock_sc = MagicMock()
            mock_sc.execution_context.get_origin_info.return_value = {"type": "unknown"}
            mock_sc_cls.return_value = mock_sc

            result = await create_tool.function(
                mock_ctx, cron="0 9 * * 1", task="weekly report"
            )

        mock_registered.assert_called_once_with("unknown")
        assert "not supported" in result
        assert "unknown" in result
        mock_create.assert_not_called()

    # -- End-to-end tests against the real origin-factory registry -----------
    #
    # These tests exercise the actual core.context_factory state instead of
    # mocking ``is_origin_factory_registered``, proving that registering a
    # new origin type unblocks scheduling and that an unregistered type is
    # refused regardless of whether it is the "unknown" sentinel.

    @pytest.mark.asyncio
    async def test_create_succeeds_for_real_registered_origin(
        self, clean_origin_registry
    ):
        """Registering an origin in the real registry makes scheduling succeed."""

        def _factory(_info, _cfg, _prompts):
            return MagicMock()

        clean_origin_registry.register_origin_factory("platform_x", _factory)

        tools = get_tool_registrations()
        create_tool = next(t for t in tools if t.name == "create_schedule")
        mock_ctx = MagicMock()

        with (
            patch("skills.scheduler.tools.SkillContext") as mock_sc_cls,
            patch("skills.scheduler.skill.create_schedule") as mock_create,
        ):
            mock_sc = MagicMock()
            mock_sc.execution_context.get_origin_info.return_value = {
                "type": "platform_x",
                "channel_id": "C1",
            }
            mock_sc_cls.return_value = mock_sc
            mock_create.return_value = {
                "id": "sched-1",
                "cron": "0 9 * * 1",
                "task": "report",
            }

            result = await create_tool.function(
                mock_ctx, cron="0 9 * * 1", task="report"
            )

        assert "sched-1" in result
        mock_create.assert_called_once_with(
            cron="0 9 * * 1",
            task="report",
            origin_info={"type": "platform_x", "channel_id": "C1"},
        )

    @pytest.mark.asyncio
    async def test_create_refuses_unregistered_origin_via_real_registry(
        self,
        clean_origin_registry,  # noqa: ARG002 — fixture ensures registry is empty
    ):
        """An origin type not in the real registry is refused without mocking."""
        # Registry is empty (clean_origin_registry cleared it) — no factory
        # for "platform_x" or anything else.
        tools = get_tool_registrations()
        create_tool = next(t for t in tools if t.name == "create_schedule")
        mock_ctx = MagicMock()

        with (
            patch("skills.scheduler.tools.SkillContext") as mock_sc_cls,
            patch("skills.scheduler.skill.create_schedule") as mock_create,
        ):
            mock_sc = MagicMock()
            mock_sc.execution_context.get_origin_info.return_value = {
                "type": "platform_x"
            }
            mock_sc_cls.return_value = mock_sc

            result = await create_tool.function(
                mock_ctx, cron="0 9 * * 1", task="report"
            )

        assert "not supported" in result
        assert "platform_x" in result
        mock_create.assert_not_called()


class TestListSchedulesTool:
    """The tool lists only the calling conversation's schedules."""

    def _list_tool(self):
        return next(t for t in get_tool_registrations() if t.name == "list_schedules")

    def _with_origin(self, origin_info):
        mock_sc = MagicMock()
        mock_sc.execution_context.get_origin_info.return_value = origin_info
        return patch("skills.scheduler.tools.SkillContext", return_value=mock_sc)

    @pytest.mark.asyncio
    async def test_list_empty(self):
        with (
            self._with_origin({"type": "slack", "channel_id": "C1"}),
            patch("skills.scheduler.skill.list_schedules", return_value=[]),
        ):
            result = await self._list_tool().function(MagicMock())

        assert "No scheduled tasks" in result

    @pytest.mark.asyncio
    async def test_list_with_entries(self):
        with (
            self._with_origin({"type": "slack", "channel_id": "C1"}),
            patch(
                "skills.scheduler.skill.list_schedules",
                return_value=[
                    {
                        "id": "abc",
                        "cron": "0 9 * * *",
                        "task": "daily",
                        "origin_info": {"type": "slack", "channel_id": "C1"},
                    },
                ],
            ),
        ):
            result = await self._list_tool().function(MagicMock())

        assert "abc" in result
        assert "0 9 * * *" in result
        assert "slack" in result

    @pytest.mark.asyncio
    async def test_other_channels_are_not_listed(self):
        """A schedule made in a private channel must not leak its task text."""
        with (
            self._with_origin({"type": "slack", "channel_id": "C-public"}),
            patch(
                "skills.scheduler.skill.list_schedules",
                return_value=[
                    {
                        "id": "mine",
                        "cron": "0 9 * * *",
                        "task": "public task",
                        "origin_info": {"type": "slack", "channel_id": "C-public"},
                    },
                    {
                        "id": "theirs",
                        "cron": "0 9 * * *",
                        "task": "secret board briefing",
                        "origin_info": {"type": "slack", "channel_id": "C-private"},
                    },
                ],
            ),
        ):
            result = await self._list_tool().function(MagicMock())

        assert "mine" in result
        assert "theirs" not in result
        assert "secret board briefing" not in result


class TestDeleteScheduleTool:
    def _delete_tool(self):
        return next(t for t in get_tool_registrations() if t.name == "delete_schedule")

    def _with_origin(self, origin_info):
        mock_sc = MagicMock()
        mock_sc.execution_context.get_origin_info.return_value = origin_info
        return patch("skills.scheduler.tools.SkillContext", return_value=mock_sc)

    @pytest.mark.asyncio
    async def test_delete_success(self):
        with (
            self._with_origin({"type": "slack", "channel_id": "C1"}),
            patch(
                "skills.scheduler.skill.delete_schedule_in_scope", return_value=True
            ) as mock_delete,
        ):
            result = await self._delete_tool().function(
                MagicMock(), schedule_id="abc123"
            )

        assert "Deleted" in result
        assert "abc123" in result
        mock_delete.assert_called_once_with(
            "abc123", {"type": "slack", "channel_id": "C1"}
        )

    @pytest.mark.asyncio
    async def test_delete_not_found(self):
        with (
            self._with_origin({"type": "slack", "channel_id": "C1"}),
            patch(
                "skills.scheduler.skill.delete_schedule_in_scope", return_value=False
            ),
        ):
            result = await self._delete_tool().function(MagicMock(), schedule_id="nope")

        assert "not found" in result

    @pytest.mark.asyncio
    async def test_out_of_scope_reports_as_not_found(self):
        """Refusal and absence must be indistinguishable to the caller."""
        with (
            self._with_origin({"type": "slack", "channel_id": "C-other"}),
            patch(
                "skills.scheduler.skill.delete_schedule_in_scope", return_value=False
            ),
        ):
            result = await self._delete_tool().function(
                MagicMock(), schedule_id="belongs-elsewhere"
            )

        assert "not found" in result
