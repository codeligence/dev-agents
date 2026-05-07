#!/usr/bin/env python3
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
import asyncio
import json
import os
import signal
import sys
import threading

from dotenv import find_dotenv, load_dotenv
from nats.aio.msg import Msg
from pydantic import ValidationError

from core.config import get_default_config
from core.log import get_logger, setup_thread_logging
from integrations.nats.config import NatsConfig
from integrations.nats.models import SubmitJobRequest
from integrations.nats.nats_client_service import NatsClientService

# Load environment variables
load_dotenv(find_dotenv(usecwd=True))

# Set up logging
base_config = get_default_config()
enable_console = bool(os.environ.get("DEV_AGENTS_CONSOLE_LOGGING"))
setup_thread_logging(base_config, enable_console_logging=enable_console)
logger = get_logger("NatsService", level="INFO")


ActionHandler = Callable[[Msg], Awaitable[dict[str, Any] | None]]


class NatsService:
    """Service for handling NATS job messages.

    Subscribes to ``{prefix}.{job_id}.>`` and dispatches on the trailing
    action segment. Each handler owns its own payload parsing, so request
    models stay action-specific instead of sharing one god-struct.
    """

    def __init__(self, nats_client: NatsClientService, job_id: str):
        """Initialize NATS service.

        Args:
            nats_client: NATS client service instance
            job_id: Unique identifier for this job (used in subject subscription)
        """
        self.nats_client = nats_client
        self.job_id = job_id
        self.logger = get_logger("NatsService", level="INFO")
        self.shutdown_event = asyncio.Event()

        self._handlers: dict[str, ActionHandler] = {
            "list-skills": self._handle_list_skills,
            "submit": self._handle_submit_job,
        }

    def _ensure_prompts_directory(self) -> Path:
        """Ensure the prompts directory exists."""
        prompts_dir = Path("prompts")
        prompts_dir.mkdir(exist_ok=True)
        return prompts_dir

    @staticmethod
    def _extract_action_from_subject(subject: str) -> str | None:
        """Return the trailing action segment of a semantic subject.

        ``jobs.<id>.submit`` → ``"submit"``. Returns ``None`` for subjects
        with fewer than three segments so the dispatcher can reject them
        cleanly.
        """
        parts = subject.split(".")
        if len(parts) < 3:
            return None
        return parts[-1]

    async def _dispatch(self, msg: Msg) -> None:
        """Route an incoming NATS message to its action handler."""
        action = self._extract_action_from_subject(msg.subject)
        if action is None:
            self.logger.warning(f"Malformed subject, no action: {msg.subject}")
            await self._reply(msg, {"ok": False, "error": "missing action"})
            return

        handler = self._handlers.get(action)
        if handler is None:
            self.logger.warning(f"Unknown action '{action}' on subject {msg.subject}")
            await self._reply(msg, {"ok": False, "error": "unknown action"})
            return

        try:
            result = await handler(msg)
        except ValidationError as e:
            self.logger.warning(
                f"Invalid payload for action '{action}' on "
                f"{msg.subject}: {e.errors()}"
            )
            await self._reply(msg, {"ok": False, "error": "invalid payload"})
            return
        except Exception as e:
            self.logger.error(f"Error handling '{action}' on {msg.subject}: {e}")
            await self._reply(msg, {"ok": False, "error": "internal error"})
            return

        if result is not None:
            await self._reply(msg, result)

    async def _reply(self, msg: Msg, payload: dict[str, Any]) -> None:
        """Send ``payload`` as a JSON reply when the message has a reply subject."""
        if not msg.reply:
            return
        try:
            await msg.respond(json.dumps(payload).encode())
        except Exception as e:
            self.logger.debug(f"Failed to send reply on {msg.reply}: {e}")

    async def _handle_list_skills(self, _msg: Msg) -> dict[str, Any]:
        """Return the list of enabled skills from configuration.

        The payload is currently empty; no parsing needed.
        """
        config = get_default_config()
        enabled: list[str] = config.get_value("skills.enable", [])
        skills = [{"name": name} for name in enabled]
        self.logger.info(f"list-skills: returning {len(skills)} skill(s)")
        return {"ok": True, "skills": skills}

    async def _handle_submit_job(self, msg: Msg) -> dict[str, Any]:
        """Accept a job and run the long-running work in the background."""
        job = SubmitJobRequest.model_validate_json(msg.data)
        self.logger.info(f"Received job {job.id} for project '{job.project}'")
        asyncio.create_task(self._process_job(job))
        return {"ok": True, "message": f"Job {job.id} accepted"}

    async def _process_job(self, job: SubmitJobRequest) -> None:
        """Process a job asynchronously."""
        try:
            updates_subject = self.nats_client.config.get_subject_job_updates()
            await self.nats_client.publish(updates_subject, f"started: {job.id}")

            prompts_dir = self._ensure_prompts_directory()
            prompt_file = prompts_dir / job.id
            prompt_file.write_text(job.prompt)
            self.logger.info(f"Wrote prompt for job {job.id} to {prompt_file}")

            await asyncio.sleep(0.5)

            await self.nats_client.publish(updates_subject, f"finished: {job.id}")
            self.logger.info(f"Completed job {job.id}")

        except Exception as e:
            self.logger.error(f"Error processing job {job.id}: {e}")
            try:
                updates_subject = self.nats_client.config.get_subject_job_updates()
                await self.nats_client.publish(updates_subject, f"error: {job.id}")
            except Exception as publish_error:
                self.logger.debug(
                    f"Failed to publish error notification: {publish_error}"
                )

    async def start(self) -> None:
        """Start the NATS service and listen for messages."""
        try:
            await self.nats_client.connect()

            full_subject = self.nats_client.config.subject_wildcard_for_job(self.job_id)
            await self.nats_client.subscribe(full_subject, cb=self._dispatch)

            self.logger.info(
                f"NATS job '{self.job_id}' listening on subject: {full_subject}"
            )

            await self.shutdown_event.wait()

        except Exception as e:
            self.logger.error(f"Error in NATS service: {e}")
            raise
        finally:
            await self.nats_client.disconnect()

    def shutdown(self) -> None:
        """Signal the service to shutdown gracefully."""
        self.logger.info("Shutdown signal received")
        self.shutdown_event.set()


# Global service instance for signal handlers
_service_instance: NatsService | None = None


def _signal_handler(signum: int, _frame: object) -> None:
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, initiating shutdown...")
    if _service_instance:
        _service_instance.shutdown()


def _create_service() -> NatsService | None:
    """Load configuration and build a :class:`NatsService`.

    Returns ``None`` and logs the reason if configuration is missing or the
    NATS client cannot be initialised. Shared by both :func:`main` and
    :func:`start_service`.
    """
    try:
        nats_config = NatsConfig(base_config)
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        return None

    if not nats_config.is_configured():
        logger.error(
            "Missing NATS configuration. Please set NATS_SERVER_URL "
            "and NATS_JOB_ID environment variables."
        )
        return None

    job_id = nats_config.get_job_id()
    if not job_id:
        logger.error("Job ID is required but not configured.")
        return None

    logger.info(f"Configured for NATS server: {nats_config.get_server_url()}")
    logger.info(f"Job ID: {job_id}")

    try:
        nats_client = NatsClientService(nats_config)
    except Exception as e:
        logger.error(f"Error initializing NATS client: {e}")
        return None

    return NatsService(nats_client, job_id)


def main() -> None:
    """Main entry point for the NATS service."""
    global _service_instance

    logger.info("Starting NATS Service")

    service = _create_service()
    if service is None:
        sys.exit(1)

    _service_instance = service

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    try:
        asyncio.run(service.start())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Error in service: {e}")
        sys.exit(1)
    finally:
        logger.info("NATS Service shut down")


def start_service(shutdown_event: threading.Event) -> None:
    """Start the NATS service, managed by the orchestrator.

    Args:
        shutdown_event: Shared shutdown event from the orchestrator.
            When set, the service should shut down gracefully.
    """
    logger.info("Starting NATS Service (orchestrated)")

    service = _create_service()
    if service is None:
        return

    def _watch_shutdown() -> None:
        shutdown_event.wait()
        service.shutdown()

    watcher = threading.Thread(target=_watch_shutdown, daemon=True)
    watcher.start()

    try:
        asyncio.run(service.start())
    except Exception as e:
        logger.error(f"Error in NATS service: {e}")
    finally:
        logger.info("NATS Service shut down")


if __name__ == "__main__":
    main()
