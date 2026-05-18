"""Entrypoint service for non-Slack messaging platforms (Email, Mattermost, Telegram).

Bridges the ServiceOrchestrator's thread-based model with the async platform
services.  Runs an asyncio event loop in the orchestrator thread, starts all
detected platforms, and shuts them down when the shared shutdown event fires.
"""

import asyncio
import os
import threading

from dotenv import load_dotenv

from core.agents.service import AgentService
from core.config import get_default_config
from core.log import get_logger, setup_thread_logging

load_dotenv()

base_config = get_default_config()
enable_console = bool(os.environ.get("DEV_AGENTS_CONSOLE_LOGGING"))
setup_thread_logging(base_config, enable_console_logging=enable_console)
logger = get_logger("PlatformsEntrypoint", level="INFO")


def start_service(shutdown_event: threading.Event) -> None:
    """Start all detected platform services, managed by the orchestrator.

    Args:
        shutdown_event: Shared shutdown event from the orchestrator.
            When set, all platform services are stopped gracefully.
    """
    logger.info("Starting platforms entrypoint (orchestrated)")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(_run(shutdown_event))
    except Exception:
        logger.exception("Platforms entrypoint crashed")
    finally:
        loop.close()
        logger.info("Platforms entrypoint stopped")


async def _run(shutdown_event: threading.Event) -> None:
    """Async entry: start platforms, wait for shutdown, then stop them."""
    from integrations.platforms import start_platforms, stop_platforms

    # Create an AgentService and register agents (same pattern as other entrypoints)
    agent_service = AgentService()
    _register_agents(agent_service)

    await start_platforms(agent_service)

    # Wait for the orchestrator's shutdown event in a non-blocking way
    await asyncio.get_event_loop().run_in_executor(None, shutdown_event.wait)

    logger.info("Shutdown event received, stopping platforms...")
    await stop_platforms()


def _register_agents(agent_service: AgentService) -> None:
    """Register available agents with the service."""
    from agents.agents.gitchatbot.agent import AGENT_NAME, GitChatbotAgent

    def create_chatbot_agent() -> type[GitChatbotAgent]:
        return GitChatbotAgent

    agent_service.register_agent(AGENT_NAME, create_chatbot_agent)
    logger.info(f"Registered agents: {AGENT_NAME}")
