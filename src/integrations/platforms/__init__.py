"""Platform registry — detect, start, and stop non-Slack platform services."""

from __future__ import annotations

from typing import Any
import os

from core.log import get_logger
from integrations.platforms.agent_context import PlatformAgentContext
from integrations.platforms.base import BasePlatformService, PlatformMessage

logger = get_logger("integrations.platforms")

__all__ = [
    "BasePlatformService",
    "PlatformAgentContext",
    "PlatformMessage",
    "detect_platforms",
    "start_platforms",
    "stop_platforms",
]

# Active service instances (populated by start_platforms)
_services: list[BasePlatformService] = []


_REQUIRED_ENV: dict[str, tuple[str, ...]] = {
    "email": ("EMAIL_ADDRESS", "EMAIL_PASSWORD", "EMAIL_IMAP_HOST", "EMAIL_SMTP_HOST"),
    "mattermost": ("MATTERMOST_URL", "MATTERMOST_TOKEN"),
    "telegram": ("TELEGRAM_BOT_TOKEN",),
}


def detect_platforms() -> list[str]:
    """Return names of platforms whose required env vars are set."""
    return [
        name
        for name, required in _REQUIRED_ENV.items()
        if all(os.environ.get(v) for v in required)
    ]


def _create_service(name: str) -> BasePlatformService:
    """Lazily import and instantiate a platform service by name."""
    if name == "email":
        from integrations.platforms.email import EmailService

        return EmailService()
    elif name == "mattermost":
        from integrations.platforms.mattermost import MattermostService

        return MattermostService()
    elif name == "telegram":
        from integrations.platforms.telegram import TelegramService

        return TelegramService()
    else:
        raise ValueError(f"Unknown platform: {name}")


async def start_platforms(agent_service: Any) -> None:
    """Detect configured platforms and start their services.

    Called from ``skill.py`` when the agent service is created.
    """
    names = detect_platforms()
    if not names:
        logger.info("No additional platforms detected (set env vars to enable)")
        return

    logger.info(f"Detected platforms: {', '.join(names)}")

    for name in names:
        try:
            svc = _create_service(name)
            svc.set_agent_service(agent_service)
            await svc.start()
            _services.append(svc)
            logger.info(f"Platform '{name}' started")
        except Exception:
            logger.exception(f"Failed to start platform '{name}'")


async def stop_platforms() -> None:
    """Gracefully stop all running platform services."""
    for svc in _services:
        try:
            await svc.stop()
        except Exception:
            logger.exception(f"Error stopping platform '{svc.name}'")
    _services.clear()
    logger.info("All platforms stopped")
