#!/usr/bin/env python3
import os
import threading
import traceback

from dotenv import load_dotenv

from core.config import get_default_config
from core.log import get_logger, setup_thread_logging
from entrypoints.slack_entrypoint.agent_message_consumer import AgentMessageConsumer
from entrypoints.slack_entrypoint.slack_bot_service import SlackBotService
from integrations.slack.models import SlackBotConfig
from integrations.slack.slack_client_service import SlackClientService

# Load environment variables
load_dotenv()

# Set up logging
base_config = get_default_config()
# Check for verbose logging from main entrypoint
enable_console = bool(os.environ.get("DEV_AGENTS_CONSOLE_LOGGING"))
setup_thread_logging(base_config, enable_console_logging=enable_console)
logger = get_logger("SlackBot", level="INFO")


def main() -> None:
    """Main entry point for the Slack bot."""
    logger.info("Starting Slack Bot")

    # Load configuration
    try:
        slack_config = SlackBotConfig(base_config)

        if not slack_config.is_configured():
            logger.error(
                "Missing Slack configuration. Please set SLACK_BOT_TOKEN "
                "and SLACK_APP_TOKEN environment variables"
            )
            return

        logger.info("Slack configuration validated")

    except Exception as e:
        logger.error(f"Error loading configuration: {str(e)}")
        return

    # Initialize Slack client for the agent consumer
    slack_client = SlackClientService(
        slack_config,
        max_connection_failures=slack_config.get_max_connection_failures(),
    )

    # Initialize agent-based consumer
    consumer = AgentMessageConsumer(slack_client=slack_client, config=base_config)

    # Initialize and start bot service
    bot_service = SlackBotService(
        consumer=consumer,
        slack_client=slack_client,
        processing_timeout=slack_config.get_processing_timeout(),
    )

    try:
        bot_service.start()  # Now synchronous
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"Error in main loop: {str(e)}\n{error_traceback}")
    finally:
        logger.info("Slack Bot shutting down")


def start_service(shutdown_event: threading.Event) -> None:
    """Start the Slack bot service, managed by the orchestrator.

    Args:
        shutdown_event: Shared shutdown event from the orchestrator.
            When set, the service should shut down gracefully.
    """
    logger.info("Starting Slack Bot (orchestrated)")

    # Load configuration
    try:
        slack_config = SlackBotConfig(base_config)

        if not slack_config.is_configured():
            logger.error(
                "Missing Slack configuration. Please set SLACK_BOT_TOKEN "
                "and SLACK_APP_TOKEN environment variables"
            )
            return

        logger.info("Slack configuration validated")

    except Exception as e:
        logger.error(f"Error loading configuration: {str(e)}")
        return

    # Initialize Slack client for the agent consumer
    slack_client = SlackClientService(
        slack_config,
        max_connection_failures=slack_config.get_max_connection_failures(),
    )

    # Initialize agent-based consumer
    consumer = AgentMessageConsumer(slack_client=slack_client, config=base_config)

    # Initialize bot service without signal handlers (orchestrator handles signals)
    bot_service = SlackBotService(
        consumer=consumer,
        slack_client=slack_client,
        processing_timeout=slack_config.get_processing_timeout(),
        register_signal_handlers=False,
    )

    # Watcher thread: bridge external shutdown_event to bot_service.shutdown()
    def _watch_shutdown() -> None:
        shutdown_event.wait()
        bot_service.shutdown()

    watcher = threading.Thread(target=_watch_shutdown, daemon=True)
    watcher.start()

    try:
        bot_service.start()  # Blocks until internal shutdown_event is set
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"Error in Slack bot: {str(e)}\n{error_traceback}")
    finally:
        logger.info("Slack Bot shutting down")


if __name__ == "__main__":
    main()  # Direct call, no asyncio.run needed
