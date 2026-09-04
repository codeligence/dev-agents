"""Scheduler skill — persistent cron-like task scheduling.

Hooks into the agent service lifecycle to capture references needed for
job execution, then starts APScheduler with all persisted schedules.

Tools are exposed two ways:
- ``gitchatbot.register_tools`` action — PydanticAI ToolRegistrations for
  the gitchatbot agent.
- ``claude_code_subagent.collect_tools`` filter — Claude Agent SDK MCP
  tools for Claude Code SDK subagents.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from core.config import get_default_config
from core.hooks import hooks
from core.log import get_logger
from core.storage import get_storage

if TYPE_CHECKING:
    from core.agents.models import ToolRegistration
    from skills.scheduler.service import SchedulerService
    from skills.scheduler.storage import ScheduleStorage

logger = get_logger("skills.scheduler")

# Module-level singleton — initialised in setup(), used by management helpers.
_service: SchedulerService | None = None
_storage: ScheduleStorage | None = None


def _register_tools(registrations: list[ToolRegistration]) -> None:
    """Action hook: append scheduler tools to agent tool list."""
    from skills.scheduler.tools import get_tool_registrations

    registrations.extend(get_tool_registrations())


def _register_mcp_tools(
    registrations: list[tuple[str, list[Any]]],
) -> list[tuple[str, list[Any]]]:
    """Filter hook: append scheduler MCP tools for Claude Code SDK subagents.

    Silently skips when ``claude-agent-sdk`` is not installed so installations
    without the ``[claude]`` extra continue to work.
    """
    try:
        from skills.scheduler.mcp_tools import create_mcp_tools
    except ImportError:
        logger.debug(
            "claude-agent-sdk not installed; skipping scheduler MCP tool registration"
        )
        return registrations

    registrations.append(create_mcp_tools())
    return registrations


def _on_agent_service_created(agent_service: object) -> None:
    """Capture the AgentService so scheduled jobs can reuse it."""
    if _service is not None:
        _service.set_agent_service(agent_service)  # type: ignore[arg-type]
        logger.info("Scheduler: captured AgentService reference")


def setup() -> None:
    """Initialise scheduler storage + service and register hooks."""
    global _service, _storage

    from skills.scheduler.service import SchedulerService
    from skills.scheduler.storage import ScheduleStorage

    config = get_default_config()

    storage = get_storage(config)
    _storage = ScheduleStorage(storage)
    _service = SchedulerService(
        schedule_storage=_storage,
        config=config,
    )

    # Hook into agent service creation to grab the reference
    hooks().add_action("agent_service.created", _on_agent_service_created)

    # Register PydanticAI tools (gitchatbot agent path)
    hooks().add_action("gitchatbot.register_tools", _register_tools)

    # Register Claude Agent SDK MCP tools (Claude Code subagent path)
    hooks().add_filter("claude_code_subagent.collect_tools", _register_mcp_tools)

    # Start scheduler (loads persisted jobs)
    _service.start()
    logger.info("Scheduler skill: setup complete")


# ---------------------------------------------------------------------------
# Public management API — called by tools at runtime
# ---------------------------------------------------------------------------


def create_schedule(
    *,
    cron: str,
    task: str,
    origin_info: dict[str, Any],
) -> dict[str, Any]:
    """Create a new scheduled task. Returns the schedule entry dict."""
    if _storage is None or _service is None:
        raise RuntimeError("Scheduler not initialised")

    from skills.scheduler.service import validate_cron

    validate_cron(cron)  # raises ValueError on bad input

    entry = _storage.create(
        {
            "cron": cron,
            "task": task,
            "origin_info": origin_info,
        }
    )
    _service.add_schedule(entry)
    return entry.to_dict()


def list_schedules() -> list[dict[str, Any]]:
    """Return all persisted schedules."""
    if _storage is None:
        return []
    return [e.to_dict() for e in _storage.list_all()]


def delete_schedule(schedule_id: str) -> bool:
    """Delete a schedule by ID. Returns True if it existed."""
    if _storage is None or _service is None:
        return False
    _service.remove_schedule(schedule_id)
    return _storage.delete(schedule_id)


# ---------------------------------------------------------------------------
# Conversation scoping — the authorization boundary for the agent-facing tools
# ---------------------------------------------------------------------------
#
# Schedules carry the origin of the conversation that created them, and firing
# one posts into that conversation. Left unscoped, the agent tools let anyone
# who can talk to the bot in one channel read the task text of schedules made
# in another (including private ones), delete them, or aim new output at them.
# Both tool surfaces (PydanticAI and MCP) therefore go through the helpers
# below rather than the unrestricted list/delete above, which stay for the
# scheduler service itself.


def _conversation_key(origin_info: dict[str, Any]) -> tuple[str, str]:
    """Identity of the conversation a schedule belongs to.

    Thread is deliberately not part of the key: schedules made in a channel
    are visible to that channel, not sealed inside the thread that created
    them. Contexts without a channel (CLI) collapse to one scope per type,
    which matches how little separation those contexts have anyway.
    """
    return (
        str(origin_info.get("type", "unknown")),
        str(origin_info.get("channel_id", "")),
    )


def get_schedule(schedule_id: str) -> dict[str, Any] | None:
    """Return a single schedule entry, or ``None`` when it does not exist."""
    if _storage is None:
        return None
    entry = _storage.get(schedule_id)
    return entry.to_dict() if entry is not None else None


def schedules_in_scope(origin_info: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the schedules belonging to *origin_info*'s conversation."""
    key = _conversation_key(origin_info)
    return [
        entry
        for entry in list_schedules()
        if _conversation_key(entry.get("origin_info", {})) == key
    ]


def delete_schedule_in_scope(schedule_id: str, origin_info: dict[str, Any]) -> bool:
    """Delete *schedule_id* only if it belongs to *origin_info*'s conversation.

    Returns ``False`` both for a missing schedule and for one owned by another
    conversation — callers report the two identically, so the tool cannot be
    used to probe which IDs exist elsewhere.
    """
    entry = get_schedule(schedule_id)
    if entry is None:
        return False
    if _conversation_key(entry.get("origin_info", {})) != _conversation_key(
        origin_info
    ):
        logger.warning(
            "Refused cross-conversation delete of schedule %s (owner=%s, caller=%s)",
            schedule_id,
            _conversation_key(entry.get("origin_info", {})),
            _conversation_key(origin_info),
        )
        return False
    return delete_schedule(schedule_id)
