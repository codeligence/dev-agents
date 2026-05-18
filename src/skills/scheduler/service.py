"""Scheduler service — APScheduler backed by dev-agents storage.

Loads persisted schedules on boot, executes jobs by recreating the
original entrypoint context via the context factory and running the
full agent pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import asyncio

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from core.agents.service import AgentService
from core.config import BaseConfig, get_default_config
from core.context_factory import create_context_from_origin
from core.log import get_logger
from core.prompts import get_default_prompts

if TYPE_CHECKING:
    from core.message import MessageList
    from skills.scheduler.storage import ScheduleEntry, ScheduleStorage

logger = get_logger("skills.scheduler.service")


def validate_cron(expression: str) -> CronTrigger:
    """Validate and parse a 5-field cron expression. Raises ValueError on bad input."""
    return CronTrigger.from_crontab(expression)


class SchedulerService:
    """Manages APScheduler lifecycle and bridges jobs to agent execution."""

    def __init__(
        self,
        schedule_storage: ScheduleStorage,
        config: BaseConfig | None = None,
    ) -> None:
        self._store = schedule_storage
        self._config = config or get_default_config()
        self._scheduler = BackgroundScheduler(daemon=True)
        self._agent_service: AgentService | None = None

    # -- lifecycle --

    def set_agent_service(self, agent_service: AgentService) -> None:
        self._agent_service = agent_service

    def start(self) -> None:
        """Load persisted schedules, start the scheduler, and begin auto-sync."""
        self._sync_from_storage()
        self._scheduler.start()
        self._scheduler.add_job(
            func=self._sync_from_storage,
            trigger="interval",
            seconds=30,
            id="_scheduler_sync",
            replace_existing=True,
        )
        logger.info("Scheduler started with auto-sync every 30s")

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down")

    # -- storage sync --

    def _sync_from_storage(self) -> None:
        """Reconcile APScheduler jobs with what's in storage."""
        stored = {e.id: e for e in self._store.list_all()}
        prefix = "schedule_"
        loaded_ids = {
            j.id[len(prefix) :]
            for j in self._scheduler.get_jobs()
            if j.id.startswith(prefix)
        }
        stored_ids = set(stored.keys())

        for sid in stored_ids:
            entry = stored[sid]
            if entry.enabled:
                self._add_job(entry)
            elif sid in loaded_ids:
                self.remove_schedule(sid)

        for sid in loaded_ids - stored_ids:
            self.remove_schedule(sid)

        active = sum(1 for e in stored.values() if e.enabled)
        logger.debug(
            f"Sync: {active} active schedule(s), {len(loaded_ids)} loaded job(s)"
        )

    # -- schedule management --

    def add_schedule(self, entry: ScheduleEntry) -> None:
        """Register a new schedule with APScheduler."""
        self._add_job(entry)
        logger.info(f"Added job {entry.id}: {entry.cron}")

    def remove_schedule(self, schedule_id: str) -> None:
        job_id = f"schedule_{schedule_id}"
        try:
            self._scheduler.remove_job(job_id)
            logger.info(f"Removed job {job_id}")
        except Exception:
            logger.debug(
                f"Job {job_id} not found in scheduler (may not have been loaded)"
            )

    def _add_job(self, entry: ScheduleEntry) -> None:
        try:
            trigger = validate_cron(entry.cron)
        except ValueError as e:
            logger.error(f"Invalid cron for schedule {entry.id}: {e}")
            return

        self._scheduler.add_job(
            func=self._execute_job,
            trigger=trigger,
            id=f"schedule_{entry.id}",
            args=[entry.id],
            replace_existing=True,
            misfire_grace_time=300,
        )

    # -- job execution --

    def _execute_job(self, schedule_id: str) -> None:
        """APScheduler calls this from its thread pool. Bridges to async agent."""
        entry = self._store.get(schedule_id)
        if entry is None:
            logger.warning(f"Schedule {schedule_id} not found in storage, skipping")
            return
        if not entry.enabled:
            logger.info(f"Schedule {schedule_id} is disabled, skipping")
            return

        logger.info(f"Firing schedule {schedule_id}: {entry.task[:80]}")

        try:
            asyncio.run(self._execute_agent(entry))
        except Exception as e:
            logger.error(f"Schedule {schedule_id} execution failed: {e}", exc_info=True)

    async def _execute_agent(self, entry: ScheduleEntry) -> None:
        """Recreate the original entrypoint context and run the agent pipeline."""

        config = self._config
        prompts = get_default_prompts()

        # Recreate context from the stored origin info
        context = create_context_from_origin(entry.origin_info, config, prompts)

        # Inject the task as a synthetic user message
        message_list = context.get_message_list()
        _inject_task_message(message_list, entry)

        if self._agent_service is None:
            self._agent_service = AgentService()

        # Use the default agent (gitchatbot)
        agent_types = self._agent_service.get_registered_agent_types()
        if not agent_types:
            logger.error(f"No agents registered, cannot execute schedule {entry.id}")
            return

        agent_type = agent_types[0]
        logger.info(f"Executing agent '{agent_type}' for schedule {entry.id}")
        await self._agent_service.execute_agent_by_type(agent_type, context)
        logger.info(f"Schedule {entry.id} execution completed")


def _inject_task_message(message_list: MessageList, entry: ScheduleEntry) -> None:
    """Add the scheduled task text as a user message in the message list."""
    from datetime import UTC, datetime

    from core.message import BaseMessage

    class _ScheduledMessage(BaseMessage):
        """Minimal message representing a scheduled task."""

        def __init__(self, task: str, schedule_id: str) -> None:
            self._task = task
            self._schedule_id = schedule_id
            self._ts = datetime.now(UTC)

        def get_user_name(self) -> str:
            return f"scheduler:{self._schedule_id}"

        def get_user_id(self) -> str:
            return f"scheduler:{self._schedule_id}"

        def get_message_content(self) -> str:
            return self._task

        def get_message_date(self) -> datetime:
            return self._ts

        def get_thread_id(self) -> str:
            return self._schedule_id

        def is_bot(self) -> bool:
            return False

    message_list.add_message(_ScheduledMessage(entry.task, entry.id))
