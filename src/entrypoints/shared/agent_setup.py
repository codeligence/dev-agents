"""Shared agent service instance and registration for all HTTP entrypoints.

Provides a single AgentService so that all entrypoints (AGUI, OpenAI, etc.)
share the same agent registry and any future service-level state.
"""

from core.agents.service import AgentService
from core.log import get_logger

logger = get_logger("SharedAgentSetup")

# Single shared instance — all HTTP entrypoints use this
agent_service = AgentService()
_agents_registered = False


def ensure_agents_registered() -> AgentService:
    """Register default agents once and return the shared AgentService.

    Safe to call multiple times; registration only happens on first call.
    """
    global _agents_registered
    if _agents_registered:
        return agent_service

    from agents.agents.gitchatbot.agent import AGENT_NAME, GitChatbotAgent

    def create_chatbot_agent() -> type[GitChatbotAgent]:
        return GitChatbotAgent

    agent_service.register_agent(AGENT_NAME, create_chatbot_agent)
    _agents_registered = True
    logger.info(f"Registered agents: {AGENT_NAME}")

    return agent_service
