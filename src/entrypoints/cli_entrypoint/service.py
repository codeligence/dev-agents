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


#!/usr/bin/env python3
"""CLI entrypoint for interactive command-line agent conversations."""

from pathlib import Path
from typing import cast
import argparse
import asyncio
import sys

from dotenv import load_dotenv

from agents.agents.gitchatbot.agent import AGENT_NAME
from core.agents.service import AgentService
from core.config import BaseConfig, get_default_config
from core.log import (
    get_logger,
    reset_context_token,
    set_context_token,
    setup_thread_logging,
)
from core.message import MessageList
from core.prompts import get_default_prompts
from entrypoints.cli_entrypoint.agent_context import CLIAgentContext


def _supports_color() -> bool:
    """Check if terminal supports ANSI colors."""
    return (
        hasattr(sys.stdout, "isatty")
        and sys.stdout.isatty()
        and hasattr(sys.stderr, "isatty")
        and sys.stderr.isatty()
    )


def _colorize(text: str, color_code: str) -> str:
    """Add ANSI color codes to text if terminal supports colors."""
    if _supports_color():
        return f"\033[{color_code}m{text}\033[0m"
    return text


def _green(text: str) -> str:
    """Make text green if terminal supports colors."""
    return _colorize(text, "92")  # Bright green


def _print_banner() -> None:
    """Print the Codeligence Dev Agents banner."""
    banner = """
 ██████╗ ██████╗ ██████╗ ███████╗██╗     ██╗ ██████╗ ███████╗███╗   ██╗ ██████╗███████╗
██╔════╝██╔═══██╗██╔══██╗██╔════╝██║     ██║██╔════╝ ██╔════╝████╗  ██║██╔════╝██╔════╝
██║     ██║   ██║██║  ██║█████╗  ██║     ██║██║  ███╗█████╗  ██╔██╗ ██║██║     █████╗
██║     ██║   ██║██║  ██║██╔══╝  ██║     ██║██║   ██║██╔══╝  ██║╚██╗██║██║     ██╔══╝
╚██████╗╚██████╔╝██████╔╝███████╗███████╗██║╚██████╔╝███████╗██║ ╚████║╚██████╗███████╗
 ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝╚══════╝╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝ ╚═════╝╚══════╝

██████╗ ███████╗██╗   ██╗     █████╗  ██████╗ ███████╗███╗   ██╗████████╗███████╗
██╔══██╗██╔════╝██║   ██║    ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██╔════╝
██║  ██║█████╗  ██║   ██║    ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ███████╗
██║  ██║██╔══╝  ╚██╗ ██╔╝    ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ╚════██║
██████╔╝███████╗ ╚████╔╝     ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ███████║
╚═════╝ ╚══════╝  ╚═══╝      ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝
    """

    subtitle = "Your friendly agile team servant. Happy to speak to you!"

    if _supports_color():
        # Print banner in cyan/blue
        print(_colorize(banner, "96"))  # Bright cyan
        # Print subtitle in green
        print(_colorize(f"\n{subtitle.center(80)}\n", "92"))  # Bright green
    else:
        print(banner)
        print(f"\n{subtitle.center(80)}\n")


# Load environment variables
load_dotenv()

# Set up logging (console logging will be configured based on -v flag in main)
base_config = get_default_config()
logger = get_logger("CLIEntrypoint", level="INFO")


class CLIConfig:
    """Configuration for CLI service."""

    def __init__(self, base_config: BaseConfig):
        self._base_config = base_config

    def get_default_agent_type(self) -> str:
        return cast(
            "str", self._base_config.get_value("cli.agent.defaultAgentType", AGENT_NAME)
        )


def _register_agents(agent_service: AgentService) -> None:
    """Register available agents with the service."""
    # Import and register the GitChatbot agent
    from agents.agents.gitchatbot.agent import GitChatbotAgent

    def create_chatbot_agent() -> type[GitChatbotAgent]:
        return GitChatbotAgent

    agent_service.register_agent(AGENT_NAME, create_chatbot_agent)
    logger.info("Registered agents: " + AGENT_NAME)


async def run_cli() -> None:
    """Run the interactive CLI loop."""

    # Initialize agent service and register agents
    agent_service = AgentService()
    _register_agents(agent_service)

    # Get configuration
    cli_config = CLIConfig(base_config)
    agent_type = cli_config.get_default_agent_type()

    # Initialize conversation history
    conversation_history = MessageList()
    thread_id = "cli-session"

    # Set logging context
    context_token = set_context_token(thread_id)

    try:
        # Display the banner
        _print_banner()

        print("Hello, what can I do for you?")
        print()

        # Show examples
        if _supports_color():
            print(
                _colorize("Here are some examples to get you started:", "93")
            )  # Yellow
            print(
                f"  {_colorize('•', '96')} Please tell me about issue 123"
            )  # Cyan bullet
            print(f"  {_colorize('•', '96')} Please do an impact analysis on issue 456")
            print(
                f"  {_colorize('•', '96')} Please run the guideline check on issue 789"
            )
        else:
            print("Here are some examples to get you started:")
            print("  • Please tell me about issue 123")
            print("  • Please do an impact analysis on issue 456")
            print("  • Please run the guideline check on issue 789")

        print()
        print("(Press Ctrl+D to exit)")
        print()

        while True:
            try:
                # Get user input
                user_input = input("You: ").strip()

                # Skip empty messages
                if not user_input:
                    continue

                # Create CLI agent context for this interaction
                cli_context = CLIAgentContext(
                    message_list=conversation_history,
                    config=base_config,
                    prompts=get_default_prompts(),
                    thread_id=thread_id,
                )

                # Add user message to conversation history
                cli_context.add_user_message(user_input)

                # Reprint user message in green with newlines
                print(f"\n\n{_green(f'You: {user_input}')}\n\n")

                logger.info(f"Processing user input: {user_input[:50]}...")

                try:
                    # Execute agent with full conversation history
                    await agent_service.execute_agent_by_type(
                        agent_type=agent_type, context=cli_context
                    )

                    logger.info("Agent execution completed successfully")

                except Exception as agent_error:
                    error_msg = f"Sorry, I encountered an error: {str(agent_error)}"
                    print(f"❌ {error_msg}")
                    logger.error(f"Agent execution failed: {str(agent_error)}")

            except EOFError:
                # Ctrl+D pressed
                print("\nGoodbye!")
                break
            except KeyboardInterrupt:
                # Ctrl+C pressed
                print("\nExiting...")
                break
            except Exception as input_error:
                print(f"❌ Input error: {str(input_error)}")
                logger.error(f"Input processing error: {str(input_error)}")

    finally:
        reset_context_token(context_token)


def main() -> None:
    """Main entry point for CLI application."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="CLI entrypoint for interactive agent conversations"
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging output to console",
    )
    args = parser.parse_args()

    # Configure logging based on verbosity flag
    setup_thread_logging(base_config, enable_console_logging=args.verbose)

    logger.info("Starting CLI service")

    try:
        # Print release information if available
        try:
            with Path("release.txt").open() as f:
                release_info = f.read().strip()
                logger.info(f"Release information:\\n{release_info}")
        except FileNotFoundError:
            logger.info("No release information available")
        except Exception as release_error:
            logger.warning(f"Could not read release information: {release_error}")

        # Run the CLI loop
        asyncio.run(run_cli())

    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
        sys.exit(0)
    except Exception as startup_error:
        logger.error(f"Failed to start CLI service: {str(startup_error)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
