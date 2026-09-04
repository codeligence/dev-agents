"""MCP tools for schedule management — injected into the Claude Code SDK agent.

These tools run inside the dev-agents process via the Claude Agent SDK's
in-process MCP server, so they share the live ``ScheduleStorage`` and
``SchedulerService`` with the rest of the skill. Changes made through them
take effect immediately, with no auto-sync delay.

Exposed via the ``claude_code_subagent.collect_tools`` filter hook so
Claude Code SDK subagents can manage schedules directly.

The ``claude-agent-sdk`` dependency is optional (extra: ``claude``). If
it is not installed the module raises ``ImportError`` and the caller is
expected to skip MCP tool registration gracefully.
"""

from typing import Annotated, Any, NotRequired, TypedDict

from claude_agent_sdk import tool

from core.agents.context import get_current_agent_execution_context
from core.log import get_logger

logger = get_logger("skills.scheduler.mcp_tools")

SERVER_NAME = "scheduler"


class CreateScheduleArgs(TypedDict):
    cron: Annotated[
        str,
        "5-field cron expression (minute hour day-of-month month day-of-week) "
        "interpreted in UTC. Use a fully-pinned cron for one-off runs "
        "(e.g. '30 14 15 4 *') and delete the schedule after it fires.",
    ]
    task: Annotated[
        str,
        "Instruction the agent should execute when the schedule fires. "
        "Stored verbatim and injected as a synthetic user message.",
    ]
    thread_ts: NotRequired[
        Annotated[
            str,
            "Slack timestamp of a parent message (e.g. '1779839096.711709') "
            "to post the scheduled output inside that thread. Omit to post at "
            "channel top-level — even when the schedule is being created from "
            "inside a thread. To post in the current thread, read the Slack "
            "Context line in this conversation and pass its Thread TS here.",
        ]
    ]


def _text(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": message}]}


def create_mcp_tools() -> tuple[str, list[Any]]:
    """Build Claude Agent SDK tools for schedule management.

    Returns the ``(server_name, tools)`` tuple expected by the
    ``claude_code_subagent.collect_tools`` filter hook fired by
    ``agents/subagents/claude_code/``.
    """
    tools: list[Any] = []

    @tool(  # type: ignore[untyped-decorator, unused-ignore]
        "list_schedules",
        "List the scheduled tasks created in this channel, with their IDs, "
        "cron expressions, and target.",
        {},
    )
    async def list_schedules(_args: dict[str, Any]) -> dict[str, Any]:
        from skills.scheduler.skill import schedules_in_scope

        entries = schedules_in_scope(
            get_current_agent_execution_context().get_origin_info()
        )
        if not entries:
            return _text("No scheduled tasks.")

        lines = []
        for entry in entries:
            origin = entry.get("origin_info", {})
            origin_type = origin.get("type", "unknown")
            channel = origin.get("channel_id") or "—"
            thread = origin.get("thread_ts") or "(channel-level)"
            lines.append(
                f"- **{entry['id']}** | cron=`{entry['cron']}` | "
                f"{origin_type} channel={channel} thread={thread}\n"
                f"  task: {entry['task']}"
            )
        return _text("\n\n".join(lines))

    tools.append(list_schedules)

    @tool(  # type: ignore[untyped-decorator, unused-ignore]
        "create_schedule",
        (
            "Create a new scheduled task. Cron is interpreted in UTC. The "
            "scheduled output posts in the channel this tool is called from, "
            "at top level (NO thread) — even if the tool is being called from "
            "inside a thread. Pass thread_ts (the Slack timestamp of a parent "
            "message) to post inside a specific thread in that same channel; "
            "omit it to keep the default channel-level behaviour. "
            "For one-off schedules use a fully-pinned cron like "
            "'30 14 15 4 *' (April 15, 14:30 UTC) and delete the schedule "
            "after it fires."
        ),
        CreateScheduleArgs,
    )
    async def create_schedule(args: dict[str, Any]) -> dict[str, Any]:
        from skills.scheduler.skill import create_schedule as _create

        base_origin = get_current_agent_execution_context().get_origin_info()
        if base_origin.get("type", "unknown") == "unknown":
            return _text(
                "Scheduling is not supported from this context: it cannot be "
                "recreated when the schedule fires. Scheduled tasks can only "
                "be created from contexts that support deferred execution "
                "(e.g. Slack)."
            )

        # The channel is taken from the calling context and cannot be
        # overridden: a caller able to aim scheduled output at an arbitrary
        # channel could push content from this conversation into a private
        # one. thread_ts is a free choice within that same channel, and
        # defaults to "" (channel-level) regardless of whether the current
        # context is inside a thread — schedules typically should post
        # visibly to the channel, not buried in the thread they were
        # configured from.
        origin_info: dict[str, Any] = dict(base_origin)
        origin_info["thread_ts"] = args.get("thread_ts", "") or ""

        try:
            entry = _create(
                cron=args["cron"],
                task=args["task"],
                origin_info=origin_info,
            )
        except ValueError as exc:
            return _text(f"Invalid cron expression: {exc}")
        except RuntimeError as exc:
            return _text(f"Scheduler error: {exc}")

        target = f"channel={origin_info.get('channel_id') or '—'}"
        if origin_info.get("thread_ts"):
            target += f" thread={origin_info['thread_ts']}"
        else:
            target += " (channel-level)"
        return _text(
            f"Schedule created: **{entry['id']}**\n"
            f"cron=`{entry['cron']}` | {target}\n"
            f"task: {entry['task']}"
        )

    tools.append(create_schedule)

    @tool(  # type: ignore[untyped-decorator, unused-ignore]
        "delete_schedule",
        "Delete a scheduled task by its ID. Only tasks created in this "
        "channel can be deleted.",
        {"schedule_id": str},
    )
    async def delete_schedule(args: dict[str, Any]) -> dict[str, Any]:
        from skills.scheduler.skill import delete_schedule_in_scope

        schedule_id = args["schedule_id"]
        if delete_schedule_in_scope(
            schedule_id, get_current_agent_execution_context().get_origin_info()
        ):
            return _text(f"Deleted schedule {schedule_id}")
        return _text(f"Schedule {schedule_id} not found.")

    tools.append(delete_schedule)

    logger.info(f"Built {len(tools)} scheduler MCP tool(s) for the CEO subagent")
    return SERVER_NAME, tools
