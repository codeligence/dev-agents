#!/usr/bin/env python3
from pathlib import Path
import asyncio
import os
import signal
import sys
import threading

from dotenv import load_dotenv

from core.config import get_default_config
from core.log import get_logger, setup_thread_logging
from integrations.nats.config import NatsConfig
from integrations.nats.models import NatsJob
from integrations.nats.nats_client_service import NatsClientService

# Load environment variables
load_dotenv()

# Set up logging
base_config = get_default_config()
# Check for verbose logging from main entrypoint
enable_console = bool(os.environ.get("DEV_AGENTS_CONSOLE_LOGGING"))
setup_thread_logging(base_config, enable_console_logging=enable_console)
logger = get_logger("NatsService", level="INFO")


class NatsService:
    """Service for handling NATS job messages."""

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

        # Set up message callback
        self.nats_client.set_message_callback(self._handle_job)

    def _ensure_prompts_directory(self) -> Path:
        """Ensure the prompts directory exists.

        Returns:
            Path to the prompts directory
        """
        prompts_dir = Path("prompts")
        prompts_dir.mkdir(exist_ok=True)
        return prompts_dir

    def _handle_job(self, job: NatsJob) -> None:
        """Handle incoming job message.

        Args:
            job: NatsJob instance containing job details
        """
        self.logger.info(f"Received job {job.id} for project '{job.project}'")

        # Schedule async operations in the event loop
        asyncio.create_task(self._process_job(job))

    async def _process_job(self, job: NatsJob) -> None:
        """Process a job asynchronously.

        Args:
            job: NatsJob instance to process
        """
        try:
            # Publish start notification
            updates_subject = self.nats_client.config.get_subject_job_updates()
            await self.nats_client.publish(updates_subject, f"started: {job.id}")

            # Write prompt to file
            prompts_dir = self._ensure_prompts_directory()
            prompt_file = prompts_dir / job.id
            prompt_file.write_text(job.prompt)
            self.logger.info(f"Wrote prompt for job {job.id} to {prompt_file}")

            # Simulate processing (replace with actual work if needed)
            await asyncio.sleep(0.5)

            # Publish completion notification
            await self.nats_client.publish(updates_subject, f"finished: {job.id}")
            self.logger.info(f"Completed job {job.id}")

        except Exception as e:
            self.logger.error(f"Error processing job {job.id}: {e}")
            # Optionally publish error notification
            try:
                updates_subject = self.nats_client.config.get_subject_job_updates()
                await self.nats_client.publish(updates_subject, f"error: {job.id}")
            except Exception as publish_error:
                # Log and suppress error notification failures to avoid cascading failures
                self.logger.debug(
                    f"Failed to publish error notification: {publish_error}"
                )

    async def start(self) -> None:
        """Start the NATS service and listen for messages."""
        try:
            # Connect to NATS
            await self.nats_client.connect()

            # Subscribe to job data subject with job ID
            job_data_subject = self.nats_client.config.get_subject_job_data()
            full_subject = f"{job_data_subject}.{self.job_id}"
            await self.nats_client.subscribe(full_subject)

            self.logger.info(
                f"NATS job '{self.job_id}' listening on subject: {full_subject}"
            )

            # Keep service running until shutdown
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
    """Handle shutdown signals.

    Args:
        signum: Signal number
        _frame: Current stack frame (unused)
    """
    logger.info(f"Received signal {signum}, initiating shutdown...")
    if _service_instance:
        _service_instance.shutdown()


def main() -> None:
    """Main entry point for the NATS service."""
    global _service_instance

    logger.info("Starting NATS Service")

    # Load configuration
    try:
        nats_config = NatsConfig(base_config)

        if not nats_config.is_configured():
            logger.error(
                "Missing NATS configuration. Please set NATS_SERVER_URL and NATS_JOB_ID environment variables."
            )
            sys.exit(1)

        job_id = nats_config.get_job_id()
        if not job_id:
            logger.error("Job ID is required but not configured.")
            sys.exit(1)

        logger.info(f"Configured for NATS server: {nats_config.get_server_url()}")
        logger.info(f"Job ID: {job_id}")

    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        sys.exit(1)

    # Initialize NATS client
    try:
        nats_client = NatsClientService(nats_config)
    except Exception as e:
        logger.error(f"Error initializing NATS client: {e}")
        sys.exit(1)

    # Initialize service
    _service_instance = NatsService(nats_client, job_id)

    # Set up signal handlers
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    # Run the service
    try:
        asyncio.run(_service_instance.start())
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

    # Load configuration
    try:
        nats_config = NatsConfig(base_config)

        if not nats_config.is_configured():
            logger.error(
                "Missing NATS configuration. Please set NATS_SERVER_URL "
                "and NATS_JOB_ID environment variables."
            )
            return

        job_id = nats_config.get_job_id()
        if not job_id:
            logger.error("Job ID is required but not configured.")
            return

        logger.info(f"Configured for NATS server: {nats_config.get_server_url()}")
        logger.info(f"Job ID: {job_id}")

    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        return

    # Initialize NATS client
    try:
        nats_client = NatsClientService(nats_config)
    except Exception as e:
        logger.error(f"Error initializing NATS client: {e}")
        return

    # Initialize service
    service = NatsService(nats_client, job_id)

    # Watcher thread: bridge external shutdown_event to service.shutdown()
    def _watch_shutdown() -> None:
        shutdown_event.wait()
        service.shutdown()

    watcher = threading.Thread(target=_watch_shutdown, daemon=True)
    watcher.start()

    # Run the service (blocks on asyncio event loop)
    try:
        asyncio.run(service.start())
    except Exception as e:
        logger.error(f"Error in NATS service: {e}")
    finally:
        logger.info("NATS Service shut down")


if __name__ == "__main__":
    # For standalone testing, ensure NATS_JOB_ID is set in environment
    main()
