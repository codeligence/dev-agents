"""
Models for the agent framework.

This module contains shared models used across agent implementations,
including the ToolRegistration model for extensible tool registration.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolRegistration:
    """
    Registration for a dynamically added tool.

    Tools registered via ToolRegistration can be added to agents at runtime
    using the hook system. This enables extensibility where external code
    can register additional tools without modifying the agent.

    Attributes:
        name: Tool identifier used for the function name (e.g., "create_changelog_report")
        description: Short description shown in the system prompt's capabilities list
        function: The async tool function. Must accept RunContext as first parameter.
        priority: Ordering priority for display in system prompt. Lower numbers appear first.
                  Default is 10.

    Example:
        ```python
        from core.agents.models import ToolRegistration
        from core.hooks import hooks

        async def my_tool(ctx: RunContext[MyDeps], query: str) -> str:
            '''My custom tool.'''
            return "Result"

        def register_tools(registrations: list[ToolRegistration]) -> None:
            registrations.append(ToolRegistration(
                name="my_tool",
                description="Custom analysis capability",
                function=my_tool,
                priority=50,
            ))

        hooks().add_action("gitchatbot.register_tools", register_tools)
        ```
    """

    name: str
    description: str
    function: Callable[..., Awaitable[Any]]
    priority: int = 10
