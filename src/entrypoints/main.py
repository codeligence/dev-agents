#!/usr/bin/env python3
"""Unified entrypoint that detects and launches all configured services in parallel."""

from collections.abc import Callable
from pathlib import Path
import argparse
import asyncio
import os
import signal
import sys
import threading

from dotenv import load_dotenv

from core.config import get_default_config
from core.log import get_logger, setup_thread_logging
from core.version_check import check_for_updates

# Load environment variables
load_dotenv()

# Set up basic logging first
base_config = get_default_config()
logger = get_logger("MainEntrypoint", level="INFO")


def detect_configured_services() -> list[str]:
    """Detect all configured services.

    Returns:
        List of configured service names (e.g., ['slack', 'agui']).
    """
    configured: list[str] = []

    # Check NATS configuration
    try:
        from integrations.nats.config import NatsConfig

        nats_config = NatsConfig(base_config)
        if nats_config.is_configured():
            configured.append("nats")
    except Exception as e:
        logger.debug(f"NATS configuration check failed: {e}")

    # Check Slack configuration
    try:
        from integrations.slack.models import SlackBotConfig

        slack_config = SlackBotConfig(base_config)
        if slack_config.is_configured():
            configured.append("slack")
    except Exception as e:
        logger.debug(f"Slack configuration check failed: {e}")

    # Check AGUI configuration
    try:
        from entrypoints.agui_entrypoint.service import AGUIConfig

        agui_config = AGUIConfig(base_config)
        if agui_config.is_configured():
            configured.append("agui")
    except Exception as e:
        logger.debug(f"AGUI configuration check failed: {e}")

    return configured


class ServiceOrchestrator:
    """Starts all registered services in parallel threads with shared shutdown coordination.

    One shared threading.Event is the only coordination mechanism. Any exit
    (signal, crash, clean shutdown) from any service triggers global shutdown.
    """

    def __init__(self) -> None:
        self._services: list[tuple[str, Callable[[threading.Event], None]]] = []
        self._shutdown_event = threading.Event()
        self._threads: list[threading.Thread] = []

    def add_service(
        self, name: str, start_fn: Callable[[threading.Event], None]
    ) -> None:
        """Register a service to be started.

        Args:
            name: Human-readable service name for logging.
            start_fn: Function matching the contract
                ``start_service(shutdown_event: threading.Event) -> None``.
                Must block until done or shutdown_event is set.
                Must NOT register signal handlers or set shutdown_event.
        """
        self._services.append((name, start_fn))

    def run(self) -> None:
        """Start all registered services and wait for shutdown.

        Registers SIGINT/SIGTERM handlers, starts each service in its own
        thread (wrapped so any exit sets shutdown_event), then joins all
        threads on shutdown.
        """
        if not self._services:
            logger.warning("No services registered, nothing to run")
            return

        # Register signal handlers (main thread only)
        def _signal_handler(signum: int, _frame: object) -> None:
            logger.info(f"Received signal {signum}, initiating shutdown...")
            self._shutdown_event.set()

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

        # Start each service in its own thread
        for name, start_fn in self._services:
            thread = threading.Thread(
                target=self._run_service,
                args=(name, start_fn),
                name=f"service-{name}",
                daemon=False,
            )
            self._threads.append(thread)
            logger.info(f"Starting service thread: {name}")
            thread.start()

        # Wait for shutdown signal
        try:
            self._shutdown_event.wait()
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            self._shutdown_event.set()

        logger.info("Shutdown triggered, waiting for services to stop...")

        # Join all threads with timeout
        for thread in self._threads:
            thread.join(timeout=10)
            if thread.is_alive():
                logger.warning(
                    f"Service thread {thread.name} did not stop within timeout"
                )

        logger.info("All services stopped")

    def _run_service(
        self, name: str, start_fn: Callable[[threading.Event], None]
    ) -> None:
        """Wrap a service function: any exit (clean or crash) sets shutdown_event."""
        try:
            logger.info(f"Service '{name}' started")
            start_fn(self._shutdown_event)
            logger.info(f"Service '{name}' exited cleanly")
        except Exception as e:
            logger.error(f"Service '{name}' crashed: {e}")
        finally:
            self._shutdown_event.set()


def print_release_info() -> None:
    """Print release information if available."""
    try:
        with Path("release.txt").open() as f:
            release_info = f.read().strip()
            logger.info(f"Release information:\\n{release_info}")
    except FileNotFoundError:
        logger.info("No release information available")
    except Exception as release_error:
        logger.warning(f"Could not read release information: {release_error}")


def setup_verbose_logging(verbose: bool) -> None:
    """Set up logging based on verbose flag."""
    if verbose:
        # Set environment variable for other services to pick up
        os.environ["DEV_AGENTS_CONSOLE_LOGGING"] = "1"

    # Configure logging for this process
    setup_thread_logging(base_config, enable_console_logging=verbose)


def main() -> None:
    """Main entry point that detects and launches all configured services in parallel."""

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Dev Agents - Unified entrypoint with parallel service launch",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
All configured services are started in parallel. CLI is added
automatically when a TTY is available.

Service Detection:
  NATS        - if NATS_SERVER_URL and NATS_JOB_ID are configured
  Slack Bot   - if SLACK_BOT_TOKEN and SLACK_APP_TOKEN are configured
  AG-UI Server - if agui.server.enabled=true in configuration
  CLI Chat    - if stdin is a TTY (interactive terminal)

Examples:
  %(prog)s                          # Start all configured services
  %(prog)s -v                       # Start with verbose logging
  %(prog)s --prompt "Hello"         # Run a single prompt and exit
        """.strip(),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging output to console for all services",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="Run a single prompt non-interactively and exit (useful for Docker/CI)",
    )
    args = parser.parse_args()

    # Set up logging based on verbosity flag
    setup_verbose_logging(args.verbose)

    logger.info("Dev Agents starting with unified entrypoint")
    print_release_info()

    # Check for updates (non-blocking, graceful failure)
    try:
        asyncio.run(check_for_updates())
    except Exception as e:
        logger.debug(f"Version check failed: {e}")

    # Load skills (self-registering modules that hook into agents)
    from core.skills import load_skills

    load_skills()

    # Handle single prompt mode (non-interactive, skips orchestrator)
    if args.prompt is not None:
        if not args.prompt.strip():
            logger.error("--prompt value must not be empty")
            sys.exit(1)

        from entrypoints.cli_entrypoint.service import run_single_prompt

        logger.info("Running in single-prompt mode")
        try:
            asyncio.run(run_single_prompt(args.prompt))
        except Exception as e:
            logger.error(f"Single prompt failed: {e}")
            sys.exit(1)
        sys.exit(0)

    # Detect all configured services
    configured = detect_configured_services()
    logger.info(f"Configured services: {configured if configured else '(none)'}")

    # Build orchestrator
    orchestrator = ServiceOrchestrator()

    # Register configured services (lazy imports to avoid loading unused modules)
    for service_name in configured:
        if service_name == "nats":
            from entrypoints.nats_entrypoint.service import (
                start_service as nats_start,
            )

            orchestrator.add_service("nats", nats_start)
        elif service_name == "slack":
            from entrypoints.slack_entrypoint.service import (
                start_service as slack_start,
            )

            orchestrator.add_service("slack", slack_start)
        elif service_name == "agui":
            from entrypoints.agui_entrypoint.service import (
                start_service as agui_start,
            )

            orchestrator.add_service("agui", agui_start)

    # Add CLI if stdin is a TTY
    if sys.stdin.isatty():
        from entrypoints.cli_entrypoint.service import (
            start_service as cli_start,
        )

        orchestrator.add_service("cli", cli_start)
        logger.info("TTY detected, CLI service will be started")

    if not orchestrator._services:
        logger.error(
            "No services configured and no TTY available. "
            "Please configure at least one service."
        )
        sys.exit(1)

    orchestrator.run()


if __name__ == "__main__":
    main()
