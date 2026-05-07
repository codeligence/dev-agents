#!/usr/bin/env python3
from typing import Any
import asyncio
import contextlib
import os
import signal
import threading
import traceback

from dotenv import find_dotenv, load_dotenv

from core.config import get_default_config
from core.log import get_logger, setup_thread_logging
from entrypoints.slack_entrypoint.agent_message_consumer import AgentMessageConsumer
from entrypoints.slack_entrypoint.slack_bot_runtime import SlackBotRuntime
from integrations.slack.models import SlackBotConfig
from integrations.slack.slack_client_service import SlackClientService

# Load environment variables
load_dotenv(find_dotenv(usecwd=True))

# Set up logging
base_config = get_default_config()
enable_console = bool(os.environ.get("DEV_AGENTS_CONSOLE_LOGGING"))
setup_thread_logging(base_config, enable_console_logging=enable_console)
logger = get_logger("SlackBot", level="INFO")


def _build_runtime() -> SlackBotRuntime | None:
    try:
        slack_config = SlackBotConfig(base_config)
        if not slack_config.is_configured():
            logger.error(
                "Missing Slack configuration. Please set SLACK_BOT_TOKEN "
                "and SLACK_APP_TOKEN environment variables"
            )
            return None
        logger.info("Slack configuration validated")
    except Exception as e:
        logger.error(f"Error loading configuration: {str(e)}")
        return None

    slack_client = SlackClientService(slack_config)

    # Register Slack origin factory for deferred execution (e.g. scheduler)
    from entrypoints.slack_entrypoint.agent_context import register_slack_origin_factory

    register_slack_origin_factory(slack_client)

    consumer = AgentMessageConsumer(slack_client=slack_client, config=base_config)
    return SlackBotRuntime(
        consumer=consumer,
        slack_service=slack_client,
        slack_config=slack_config,
        processing_timeout=slack_config.get_processing_timeout(),
    )


async def _run_with_shutdown(
    runtime: SlackBotRuntime,
    register_signal_handlers: bool,
    external_shutdown: dict[str, Any] | None = None,
) -> None:
    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    if external_shutdown is not None:
        external_shutdown["loop"] = loop
        external_shutdown["event"] = shutdown_event

    if register_signal_handlers:
        # add_signal_handler is unavailable on Windows; skip silently.
        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError):
                loop.add_signal_handler(sig, shutdown_event.set)

    await runtime.run(shutdown_event)


def main() -> None:
    """Main entry point for the Slack bot."""
    logger.info("Starting Slack Bot")

    runtime = _build_runtime()
    if runtime is None:
        return

    try:
        asyncio.run(_run_with_shutdown(runtime, register_signal_handlers=True))
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"Error in main loop: {str(e)}\n{error_traceback}")
    finally:
        logger.info("Slack Bot shutting down")


def start_service(shutdown_event: threading.Event) -> None:
    """Start the Slack bot service, managed by the orchestrator.

    Bridges the orchestrator's ``threading.Event`` to an inner
    ``asyncio.Event`` consumed by the runtime.
    """
    logger.info("Starting Slack Bot (orchestrated)")

    runtime = _build_runtime()
    if runtime is None:
        return

    bridge: dict[str, Any] = {}

    def _bridge_shutdown() -> None:
        shutdown_event.wait()
        loop = bridge.get("loop")
        event = bridge.get("event")
        if loop is None or event is None:
            return
        try:
            loop.call_soon_threadsafe(event.set)
        except Exception as exc:
            logger.warning(f"Failed to bridge shutdown signal: {exc}")

    watcher = threading.Thread(target=_bridge_shutdown, daemon=True)
    watcher.start()

    try:
        asyncio.run(
            _run_with_shutdown(
                runtime,
                register_signal_handlers=False,
                external_shutdown=bridge,
            )
        )
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"Error in Slack bot: {str(e)}\n{error_traceback}")
    finally:
        logger.info("Slack Bot shutting down")


if __name__ == "__main__":
    main()
