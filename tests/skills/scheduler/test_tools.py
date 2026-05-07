"""Tests for skills.scheduler.tools — PydanticAI tool registrations."""

from unittest.mock import MagicMock, patch

import pytest

from skills.scheduler.tools import get_tool_registrations


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
        import asyncio

        for tool in tools:
            assert asyncio.iscoroutinefunction(tool.function)

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
            patch("skills.scheduler.skill.create_schedule") as mock_create,
        ):
            mock_sc = MagicMock()
            mock_sc.execution_context.get_origin_info.return_value = {"type": "slack"}
            mock_sc_cls.return_value = mock_sc
            mock_create.side_effect = ValueError("bad cron")

            result = await create_tool.function(mock_ctx, cron="bad", task="test")

        assert "Invalid cron" in result


class TestListSchedulesTool:
    @pytest.mark.asyncio
    async def test_list_empty(self):
        tools = get_tool_registrations()
        list_tool = next(t for t in tools if t.name == "list_schedules")

        mock_ctx = MagicMock()

        with patch("skills.scheduler.skill.list_schedules") as mock_list:
            mock_list.return_value = []
            result = await list_tool.function(mock_ctx)

        assert "No scheduled tasks" in result

    @pytest.mark.asyncio
    async def test_list_with_entries(self):
        tools = get_tool_registrations()
        list_tool = next(t for t in tools if t.name == "list_schedules")

        mock_ctx = MagicMock()

        with patch("skills.scheduler.skill.list_schedules") as mock_list:
            mock_list.return_value = [
                {
                    "id": "abc",
                    "cron": "0 9 * * *",
                    "task": "daily",
                    "origin_info": {"type": "slack"},
                },
            ]
            result = await list_tool.function(mock_ctx)

        assert "abc" in result
        assert "0 9 * * *" in result
        assert "slack" in result


class TestDeleteScheduleTool:
    @pytest.mark.asyncio
    async def test_delete_success(self):
        tools = get_tool_registrations()
        delete_tool = next(t for t in tools if t.name == "delete_schedule")

        mock_ctx = MagicMock()

        with patch("skills.scheduler.skill.delete_schedule") as mock_delete:
            mock_delete.return_value = True
            result = await delete_tool.function(mock_ctx, schedule_id="abc123")

        assert "Deleted" in result
        assert "abc123" in result

    @pytest.mark.asyncio
    async def test_delete_not_found(self):
        tools = get_tool_registrations()
        delete_tool = next(t for t in tools if t.name == "delete_schedule")

        mock_ctx = MagicMock()

        with patch("skills.scheduler.skill.delete_schedule") as mock_delete:
            mock_delete.return_value = False
            result = await delete_tool.function(mock_ctx, schedule_id="nope")

        assert "not found" in result
