"""PydanticAI tool registrations for the scheduler skill.

Exposes create_schedule, list_schedules, and delete_schedule as agent
tools via the ``gitchatbot.register_tools`` hook.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from core.agents.models import ToolRegistration
from core.log import get_logger
from core.skills.context import SkillContext

if TYPE_CHECKING:
    from pydantic_ai import RunContext

logger = get_logger("skills.scheduler.tools")


def get_tool_registrations() -> list[ToolRegistration]:
    """Return ToolRegistration instances for all scheduler tools."""
    return [
        ToolRegistration(
            name="create_schedule",
            description=(
                "Create a new scheduled task that runs on a cron expression. "
                "The task will be executed by the agent in the same context "
                "(e.g. Slack channel) where this tool is called. "
                "For one-off schedules use a specific date cron like "
                "'30 14 15 4 *' (April 15, 14:30). "
                "Delete one-off schedules after they fire."
            ),
            function=_create_schedule,
            priority=80,
        ),
        ToolRegistration(
            name="list_schedules",
            description="List all scheduled tasks with their IDs, cron expressions, and status.",
            function=_list_schedules,
            priority=81,
        ),
        ToolRegistration(
            name="delete_schedule",
            description="Delete a scheduled task by its ID.",
            function=_delete_schedule,
            priority=82,
        ),
    ]


async def _create_schedule(
    ctx: RunContext[Any],
    cron: str,
    task: str,
) -> str:
    """Create a new scheduled task.

    Args:
        cron: 5-field cron expression (minute hour day month weekday).
        task: Description of what the agent should do when this schedule fires.

    Returns:
        Confirmation with the new schedule ID.
    """
    from skills.scheduler.skill import create_schedule

    sc = SkillContext(ctx)
    origin_info = sc.execution_context.get_origin_info()

    try:
        entry = create_schedule(cron=cron, task=task, origin_info=origin_info)
        return (
            f"Schedule created: **{entry['id']}**\n"
            f"cron=`{entry['cron']}` | task: {entry['task']}"
        )
    except ValueError as e:
        return f"Invalid cron expression: {e}"
    except RuntimeError as e:
        return f"Scheduler error: {e}"


async def _list_schedules(_ctx: RunContext[Any]) -> str:
    """List all scheduled tasks.

    Returns:
        Formatted list of all schedules, or a message if none exist.
    """
    from skills.scheduler.skill import list_schedules

    entries = list_schedules()
    if not entries:
        return "No scheduled tasks."

    lines = []
    for e in entries:
        origin_type = e.get("origin_info", {}).get("type", "unknown")
        lines.append(
            f"- **{e['id']}** | cron=`{e['cron']}` | origin={origin_type}\n"
            f"  task: {e['task']}"
        )
    return "\n\n".join(lines)


async def _delete_schedule(_ctx: RunContext[Any], schedule_id: str) -> str:
    """Delete a scheduled task by ID.

    Args:
        schedule_id: The ID of the schedule to delete.

    Returns:
        Confirmation or not-found message.
    """
    from skills.scheduler.skill import delete_schedule

    if delete_schedule(schedule_id):
        return f"Deleted schedule {schedule_id}"
    return f"Schedule {schedule_id} not found."
