#!/usr/bin/env python3
import traceback

from dotenv import load_dotenv

from core.config import BaseConfig, get_default_config
from core.log import get_logger, setup_thread_logging
from entrypoints.slack_models.agent_message_consumer import AgentMessageConsumer
from entrypoints.slack_models.slack_bot_service import SlackBotService
from integrations.slack.slack_client_service import SlackClientService

# Load environment variables
load_dotenv()

# Set up logging
base_config = get_default_config()
setup_thread_logging(base_config)
logger = get_logger("SlackBot", level="INFO")


class SlackBotConfig:
    """Configuration for Slack bot service."""

    def __init__(self, base_config: BaseConfig):
        self._base_config = base_config
        self._config_data = base_config.get_config_data()

    def get_bot_token(self) -> str:
        return self._base_config.get_value('slack.bot.botToken', '')

    def get_channel_id(self) -> str:
        return self._base_config.get_value('slack.bot.channelId', '')

    def get_app_token(self) -> str:
        return self._base_config.get_value('slack.bot.appToken', '')

    def get_processing_timeout(self) -> int:
        return int(self._base_config.get_value('slack.bot.processingTimeout', 6000))

    def is_configured(self) -> bool:
        """Check if all required Slack configuration is present."""
        return bool(self.get_bot_token() and self.get_channel_id() and self.get_app_token())


def main():
    """Main entry point for the Slack bot."""
    logger.info("Starting Slack Bot")

    # Print release information if available
    try:
        with open("release.txt", "r") as f:
            release_info = f.read().strip()
            logger.info(f"Release information:\n{release_info}")
    except Exception:
        logger.info("No release information available")

    # Load configuration
    try:
        slack_config = SlackBotConfig(base_config)

        if not slack_config.is_configured():
            logger.error(
                "Missing Slack configuration. Please set SLACK_BOT_TOKEN, "
                "SLACK_CHANNEL_ID, and SLACK_APP_TOKEN environment variables"
            )
            return

        logger.info(f"Configured for channel: {slack_config.get_channel_id()}")

    except Exception as e:
        logger.error(f"Error loading configuration: {str(e)}")
        return

    # Initialize Slack client for the agent consumer
    slack_client = SlackClientService()

    # Initialize agent-based consumer
    consumer = AgentMessageConsumer(
        slack_client=slack_client,
        config=base_config
    )

    # Initialize and start bot service
    bot_service = SlackBotService(
        consumer=consumer,
        processing_timeout=slack_config.get_processing_timeout()
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


if __name__ == "__main__":
    main()  # Direct call, no asyncio.run needed
