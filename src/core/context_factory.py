"""Registry for recreating AgentExecutionContext from serialized origin info.

Entrypoints register a factory function during startup so that deferred
execution paths (e.g. the scheduler skill) can reconstruct the correct
context type from a previously stored ``origin_info`` dict.

Usage — registering (in an entrypoint)::

    from core.context_factory import register_origin_factory

    def _slack_factory(origin_info, config, prompts):
        ...
        return SlackAgentContext(...)

    register_origin_factory("slack", _slack_factory)

Usage — recreating (in the scheduler)::

    from core.context_factory import create_context_from_origin

    ctx = create_context_from_origin(origin_info, config, prompts)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from core.log import get_logger

if TYPE_CHECKING:
    from core.config import BaseConfig
    from core.prompts import BasePrompts
    from core.protocols.agent_protocols import AgentExecutionContext

logger = get_logger("ContextFactory")

OriginFactory = Callable[
    [dict[str, Any], "BaseConfig", "BasePrompts"], "AgentExecutionContext"
]

_factories: dict[str, OriginFactory] = {}


def register_origin_factory(origin_type: str, factory: OriginFactory) -> None:
    """Register a factory that can recreate a context from origin info.

    Args:
        origin_type: The ``"type"`` value in origin_info dicts (e.g. ``"slack"``).
        factory: Callable ``(origin_info, config, prompts) -> AgentExecutionContext``.
    """
    _factories[origin_type] = factory
    logger.info(f"Registered origin factory: {origin_type}")


def create_context_from_origin(
    origin_info: dict[str, Any],
    config: BaseConfig,
    prompts: BasePrompts,
) -> AgentExecutionContext:
    """Recreate an AgentExecutionContext from a stored origin_info dict.

    Args:
        origin_info: Dict with at least a ``"type"`` key.
        config: Application configuration.
        prompts: Application prompts.

    Returns:
        A fresh AgentExecutionContext matching the original entrypoint.

    Raises:
        ValueError: If no factory is registered for the origin type.
    """
    origin_type = origin_info.get("type", "unknown")
    factory = _factories.get(origin_type)
    if factory is None:
        available = list(_factories.keys())
        raise ValueError(
            f"No context factory registered for origin type '{origin_type}'. "
            f"Available: {available}"
        )
    return factory(origin_info, config, prompts)


def get_registered_origin_types() -> list[str]:
    """Return all registered origin type names."""
    return list(_factories.keys())
