"""
WordPress-style hook system for extensibility.

This module provides a registry for actions and filters that allows code to hook
into specific points without tight coupling.

Actions are fire-and-forget events where exceptions are caught and logged.
Filters are data transformation chains where exceptions propagate up.

Usage:
    from core.hooks import hooks

    # Register an action
    hooks().add_action("user_login", lambda user_id: print(f"User {user_id} logged in"))

    # Fire an action
    hooks().do_action("user_login", user_id=123)

    # Register a filter
    hooks().add_filter("post_content", lambda content: content.upper())

    # Apply filters
    result = hooks().apply_filters("post_content", "hello world")
"""

from collections.abc import Callable
from typing import Any, TypeVar
import threading

from core.log import get_logger

T = TypeVar("T")


class HookRegistry:
    """
    Registry for actions and filters with priority-based ordering.

    Actions are callbacks that execute side effects. Exceptions are caught and logged,
    allowing remaining callbacks to continue executing.

    Filters are callbacks that transform values. Exceptions propagate up to the caller.

    Callbacks are executed in priority order (lower numbers first). Callbacks with the
    same priority are executed in registration order (FIFO).
    """

    def __init__(self) -> None:
        """Initialize the hook registry."""
        # Storage format: dict[hook_name, list[(priority, counter, callback)]]
        self._actions: dict[str, list[tuple[int, int, Callable[..., None]]]] = {}
        self._filters: dict[str, list[tuple[int, int, Callable[..., Any]]]] = {}
        self._callback_counter: int = 0
        self._logger = get_logger("hooks")

    def add_action(
        self,
        hook_name: str,
        callback: Callable[..., None],
        priority: int = 10,
    ) -> None:
        """
        Register an action callback.

        Args:
            hook_name: The name of the action hook.
            callback: The function to call when the action is fired.
            priority: Execution order; lower numbers run first. Default is 10.
        """
        if hook_name not in self._actions:
            self._actions[hook_name] = []
        self._actions[hook_name].append((priority, self._callback_counter, callback))
        self._callback_counter += 1

    def do_action(self, hook_name: str, *args: Any, **kwargs: Any) -> None:
        """
        Fire an action, calling all registered callbacks.

        Callbacks are executed in priority order. Exceptions are caught and logged,
        allowing remaining callbacks to continue executing.

        Args:
            hook_name: The name of the action hook to fire.
            *args: Positional arguments passed to callbacks.
            **kwargs: Keyword arguments passed to callbacks.
        """
        if hook_name not in self._actions:
            return

        # Sort by (priority, counter) for stable ordering
        sorted_callbacks = sorted(self._actions[hook_name], key=lambda x: (x[0], x[1]))

        for _, _, callback in sorted_callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                self._logger.exception(f"Error in action hook '{hook_name}': {e}")

    def add_filter(
        self,
        hook_name: str,
        callback: Callable[..., T],
        priority: int = 10,
    ) -> None:
        """
        Register a filter callback.

        Filter callbacks receive the value as the first argument and must return
        the (possibly modified) value.

        Args:
            hook_name: The name of the filter hook.
            callback: The function to call. Must accept value as first arg and return it.
            priority: Execution order; lower numbers run first. Default is 10.
        """
        if hook_name not in self._filters:
            self._filters[hook_name] = []
        self._filters[hook_name].append((priority, self._callback_counter, callback))
        self._callback_counter += 1

    def apply_filters(self, hook_name: str, value: T, *args: Any, **kwargs: Any) -> T:
        """
        Apply filters to a value, chaining callbacks.

        Each callback receives the current value as its first argument and must return
        the (possibly modified) value. Exceptions propagate up to the caller.

        Args:
            hook_name: The name of the filter hook.
            value: The initial value to filter.
            *args: Additional positional arguments passed to callbacks.
            **kwargs: Additional keyword arguments passed to callbacks.

        Returns:
            The filtered value after all callbacks have been applied.

        Raises:
            Exception: Any exception raised by a filter callback propagates up.
        """
        if hook_name not in self._filters:
            return value

        # Sort by (priority, counter) for stable ordering
        sorted_callbacks = sorted(self._filters[hook_name], key=lambda x: (x[0], x[1]))

        current_value = value
        for _, _, callback in sorted_callbacks:
            current_value = callback(current_value, *args, **kwargs)

        return current_value

    def remove_action(
        self,
        hook_name: str,
        callback: Callable[..., None],
    ) -> bool:
        """
        Remove a specific action callback.

        Args:
            hook_name: The name of the action hook.
            callback: The callback function to remove.

        Returns:
            True if a callback was removed, False otherwise.
        """
        if hook_name not in self._actions:
            return False

        original_len = len(self._actions[hook_name])
        self._actions[hook_name] = [
            item for item in self._actions[hook_name] if item[2] != callback
        ]

        if not self._actions[hook_name]:
            del self._actions[hook_name]

        return len(self._actions.get(hook_name, [])) < original_len

    def remove_filter(
        self,
        hook_name: str,
        callback: Callable[..., Any],
    ) -> bool:
        """
        Remove a specific filter callback.

        Args:
            hook_name: The name of the filter hook.
            callback: The callback function to remove.

        Returns:
            True if a callback was removed, False otherwise.
        """
        if hook_name not in self._filters:
            return False

        original_len = len(self._filters[hook_name])
        self._filters[hook_name] = [
            item for item in self._filters[hook_name] if item[2] != callback
        ]

        if not self._filters[hook_name]:
            del self._filters[hook_name]

        return len(self._filters.get(hook_name, [])) < original_len

    def has_action(self, hook_name: str) -> bool:
        """
        Check if an action hook has any registered callbacks.

        Args:
            hook_name: The name of the action hook.

        Returns:
            True if there are registered callbacks, False otherwise.
        """
        return hook_name in self._actions and len(self._actions[hook_name]) > 0

    def has_filter(self, hook_name: str) -> bool:
        """
        Check if a filter hook has any registered callbacks.

        Args:
            hook_name: The name of the filter hook.

        Returns:
            True if there are registered callbacks, False otherwise.
        """
        return hook_name in self._filters and len(self._filters[hook_name]) > 0

    def clear(self) -> None:
        """
        Remove all registered hooks.

        Useful for test isolation to ensure a clean state between tests.
        """
        self._actions.clear()
        self._filters.clear()
        self._callback_counter = 0


# Thread-safe singleton pattern
_hook_registry_instance: HookRegistry | None = None
_hook_registry_lock = threading.Lock()


def hooks() -> HookRegistry:
    """
    Get the global hook registry singleton.

    This function provides thread-safe access to a single HookRegistry instance
    that can be used throughout the application.

    Returns:
        The global HookRegistry instance.

    Example:
        from core.hooks import hooks

        hooks().add_action("user_login", my_callback)
        hooks().do_action("user_login", user_id=123)
    """
    global _hook_registry_instance
    if _hook_registry_instance is None:
        with _hook_registry_lock:
            if _hook_registry_instance is None:
                _hook_registry_instance = HookRegistry()
    return _hook_registry_instance
