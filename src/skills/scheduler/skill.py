"""Scheduler skill — persistent cron-like task scheduling.

Hooks into the agent service lifecycle to capture references needed for
job execution, then starts APScheduler with all persisted schedules.

Tools are exposed as PydanticAI ToolRegistrations via the
``gitchatbot.register_tools`` hook.
"""

from __future__ import annotations

from typing import Any

from core.agents.models import ToolRegistration
from core.config import get_default_config
from core.hooks import hooks
from core.log import get_logger
from core.storage import get_storage

logger = get_logger("skills.scheduler")

# Module-level singleton — initialised in setup(), used by management helpers.
_service: SchedulerService | None = None  # noqa: F821
_storage: ScheduleStorage | None = None  # noqa: F821


def _register_tools(registrations: list[ToolRegistration]) -> None:
    """Action hook: append scheduler tools to agent tool list."""
    from skills.scheduler.tools import get_tool_registrations

    registrations.extend(get_tool_registrations())


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

    # Register PydanticAI tools
    hooks().add_action("gitchatbot.register_tools", _register_tools)

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
