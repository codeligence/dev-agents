#!/usr/bin/env python3
# Copyright (C) 2025 Codeligence
#
# This file is part of Dev Agents.
#
# Dev Agents is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Dev Agents is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Dev Agents.  If not, see <https://www.gnu.org/licenses/>.


from pathlib import Path
import os
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

    # Print release information if available
    try:
        with Path("release.txt").open() as f:
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
    slack_client = SlackClientService(slack_config)

    # Initialize agent-based consumer
    consumer = AgentMessageConsumer(slack_client=slack_client, config=base_config)

    # Initialize and start bot service
    bot_service = SlackBotService(
        consumer=consumer, processing_timeout=slack_config.get_processing_timeout()
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
