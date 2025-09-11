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

"""Unified entrypoint that auto-detects and launches the appropriate service."""

from pathlib import Path
import argparse
import os
import sys

from dotenv import load_dotenv

from core.config import get_default_config
from core.log import get_logger, setup_thread_logging

# Load environment variables
load_dotenv()

# Set up basic logging first
base_config = get_default_config()
logger = get_logger("MainEntrypoint", level="INFO")


def detect_service_type() -> str:
    """Detect which service to run based on configuration.

    Priority order:
    1. Slack Bot - if SlackBotConfig.is_configured()
    2. AGUI Server - if AGUIConfig.is_configured()
    3. CLI Chat - default fallback

    Returns:
        Service type: 'slack', 'agui', or 'cli'
    """

    # Check Slack configuration
    try:
        from integrations.slack.models import SlackBotConfig

        slack_config = SlackBotConfig(base_config)
        if slack_config.is_configured():
            return "slack"
    except Exception as e:
        logger.debug(f"Slack configuration check failed: {e}")

    # Check AGUI configuration
    try:
        from entrypoints.agui_entrypoint.service import AGUIConfig

        agui_config = AGUIConfig(base_config)
        if agui_config.is_configured():
            return "agui"
    except Exception as e:
        logger.debug(f"AGUI configuration check failed: {e}")

    # Default to CLI
    return "cli"


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


def run_slack_service() -> None:
    """Run the Slack bot service."""
    logger.info("Starting Slack Bot service")

    # Import and run slack service
    from entrypoints.slack_entrypoint import service as slack_service

    slack_service.main()


def run_agui_service() -> None:
    """Run the AGUI web service."""
    logger.info("Starting AG-UI web service")

    # Import and run AGUI service
    from entrypoints.agui_entrypoint import service as agui_service

    agui_service.main()


def run_cli_service() -> None:
    """Run the CLI chat service."""
    logger.info("Starting CLI chat service")

    # Import and run CLI service
    from entrypoints.cli_entrypoint import service as cli_service

    cli_service.main()


def main() -> None:
    """Main entry point that detects and launches the appropriate service."""

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Dev Agents - Unified entrypoint with auto-service detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Service Detection Priority:
  1. Slack Bot    - if SLACK_BOT_TOKEN, SLACK_CHANNEL_ID, SLACK_APP_TOKEN are configured
  2. AG-UI Server - if agui.server.enabled=true in configuration
  3. CLI Chat     - default interactive mode

Examples:
  %(prog)s              # Auto-detect service
  %(prog)s -v           # Auto-detect with verbose logging
        """.strip(),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging output to console for all services",
    )
    args = parser.parse_args()

    # Set up logging based on verbosity flag
    setup_verbose_logging(args.verbose)

    logger.info("Dev Agents starting with unified entrypoint")
    print_release_info()

    # Detect which service to run
    service_type = detect_service_type()
    logger.info(f"Auto-detected service type: {service_type}")

    try:
        # Run the detected service
        if service_type == "slack":
            run_slack_service()
        elif service_type == "agui":
            run_agui_service()
        elif service_type == "cli":
            run_cli_service()
        else:
            logger.error(f"Unknown service type: {service_type}")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
        sys.exit(0)
    except Exception as startup_error:
        logger.error(f"Failed to start {service_type} service: {str(startup_error)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
