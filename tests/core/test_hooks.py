import pytest

from core.hooks import HookRegistry, hooks


class TestHookRegistryActions:
    """Test cases for action hooks."""

    def setup_method(self):
        """Set up a fresh registry for each test."""
        self.registry = HookRegistry()
        self.call_log: list[str] = []

    def test_add_action_basic(self):
        """Test basic action registration."""

        def callback() -> None:
            pass

        self.registry.add_action("test_hook", callback)

        assert self.registry.has_action("test_hook")

    def test_do_action_calls_callback(self):
        """Test that do_action calls registered callbacks."""

        def callback(value: str) -> None:
            self.call_log.append(value)

        self.registry.add_action("test_hook", callback)
        self.registry.do_action("test_hook", "hello")

        assert self.call_log == ["hello"]

    def test_do_action_with_kwargs(self):
        """Test that do_action passes kwargs to callbacks."""

        def callback(name: str, age: int) -> None:
            self.call_log.append(f"{name}:{age}")

        self.registry.add_action("test_hook", callback)
        self.registry.do_action("test_hook", name="Alice", age=30)

        assert self.call_log == ["Alice:30"]

    def test_do_action_multiple_callbacks(self):
        """Test that do_action calls all registered callbacks."""

        def callback1() -> None:
            self.call_log.append("callback1")

        def callback2() -> None:
            self.call_log.append("callback2")

        self.registry.add_action("test_hook", callback1)
        self.registry.add_action("test_hook", callback2)
        self.registry.do_action("test_hook")

        assert self.call_log == ["callback1", "callback2"]

    def test_do_action_priority_ordering(self):
        """Test that callbacks are called in priority order."""

        def callback_low() -> None:
            self.call_log.append("low")

        def callback_high() -> None:
            self.call_log.append("high")

        def callback_default() -> None:
            self.call_log.append("default")

        self.registry.add_action("test_hook", callback_high, priority=20)
        self.registry.add_action("test_hook", callback_low, priority=5)
        self.registry.add_action("test_hook", callback_default)  # priority=10

        self.registry.do_action("test_hook")

        assert self.call_log == ["low", "default", "high"]

    def test_do_action_same_priority_fifo(self):
        """Test that callbacks with same priority run in registration order."""

        def callback1() -> None:
            self.call_log.append("first")

        def callback2() -> None:
            self.call_log.append("second")

        def callback3() -> None:
            self.call_log.append("third")

        self.registry.add_action("test_hook", callback1, priority=10)
        self.registry.add_action("test_hook", callback2, priority=10)
        self.registry.add_action("test_hook", callback3, priority=10)

        self.registry.do_action("test_hook")

        assert self.call_log == ["first", "second", "third"]

    def test_do_action_nonexistent_hook(self):
        """Test that do_action on nonexistent hook does nothing."""
        self.registry.do_action("nonexistent_hook")
        # Should not raise, just do nothing

    def test_do_action_exception_caught_and_logged(self):
        """Test that exceptions in action callbacks are caught."""

        def failing_callback() -> None:
            raise ValueError("Test error")

        def success_callback() -> None:
            self.call_log.append("success")

        self.registry.add_action("test_hook", failing_callback, priority=5)
        self.registry.add_action("test_hook", success_callback, priority=10)

        # Should not raise, and should continue to next callback
        self.registry.do_action("test_hook")

        assert self.call_log == ["success"]


class TestHookRegistryFilters:
    """Test cases for filter hooks."""

    def setup_method(self):
        """Set up a fresh registry for each test."""
        self.registry = HookRegistry()

    def test_add_filter_basic(self):
        """Test basic filter registration."""

        def callback(x: str) -> str:
            return x

        self.registry.add_filter("test_filter", callback)

        assert self.registry.has_filter("test_filter")

    def test_apply_filters_returns_value(self):
        """Test that apply_filters returns the filtered value."""

        def uppercase(value: str) -> str:
            return value.upper()

        self.registry.add_filter("test_filter", uppercase)
        result = self.registry.apply_filters("test_filter", "hello")

        assert result == "HELLO"

    def test_apply_filters_chains_callbacks(self):
        """Test that filters are chained in sequence."""

        def add_prefix(value: str) -> str:
            return f"prefix_{value}"

        def add_suffix(value: str) -> str:
            return f"{value}_suffix"

        self.registry.add_filter("test_filter", add_prefix, priority=5)
        self.registry.add_filter("test_filter", add_suffix, priority=10)

        result = self.registry.apply_filters("test_filter", "hello")

        assert result == "prefix_hello_suffix"

    def test_apply_filters_with_extra_args(self):
        """Test that apply_filters passes extra args to callbacks."""

        def modify(value: str, multiplier: int) -> str:
            return value * multiplier

        self.registry.add_filter("test_filter", modify)
        result = self.registry.apply_filters("test_filter", "ab", 3)

        assert result == "ababab"

    def test_apply_filters_with_kwargs(self):
        """Test that apply_filters passes kwargs to callbacks."""

        def format_value(value: str, prefix: str = "", suffix: str = "") -> str:
            return f"{prefix}{value}{suffix}"

        self.registry.add_filter("test_filter", format_value)
        result = self.registry.apply_filters(
            "test_filter", "hello", prefix="[", suffix="]"
        )

        assert result == "[hello]"

    def test_apply_filters_priority_ordering(self):
        """Test that filters are applied in priority order."""

        def step1(value: list[str]) -> list[str]:
            return value + ["step1"]

        def step2(value: list[str]) -> list[str]:
            return value + ["step2"]

        def step3(value: list[str]) -> list[str]:
            return value + ["step3"]

        self.registry.add_filter("test_filter", step3, priority=30)
        self.registry.add_filter("test_filter", step1, priority=10)
        self.registry.add_filter("test_filter", step2, priority=20)

        result = self.registry.apply_filters("test_filter", [])

        assert result == ["step1", "step2", "step3"]

    def test_apply_filters_nonexistent_hook(self):
        """Test that apply_filters on nonexistent hook returns original value."""
        result = self.registry.apply_filters("nonexistent", "original")

        assert result == "original"

    def test_apply_filters_exception_propagates(self):
        """Test that exceptions in filter callbacks propagate up."""

        def failing_filter(_value: str) -> str:
            raise ValueError("Filter error")

        self.registry.add_filter("test_filter", failing_filter)

        with pytest.raises(ValueError, match="Filter error"):
            self.registry.apply_filters("test_filter", "hello")

    def test_apply_filters_preserves_type(self):
        """Test that filters can work with different types."""

        def double(value: int) -> int:
            return value * 2

        def add_ten(value: int) -> int:
            return value + 10

        self.registry.add_filter("int_filter", double, priority=5)
        self.registry.add_filter("int_filter", add_ten, priority=10)

        result = self.registry.apply_filters("int_filter", 5)

        assert result == 20  # (5 * 2) + 10


class TestHookRegistryRemoval:
    """Test cases for hook removal."""

    def setup_method(self):
        """Set up a fresh registry for each test."""
        self.registry = HookRegistry()
        self.call_log: list[str] = []

    def test_remove_action(self):
        """Test removing an action callback."""

        def callback() -> None:
            self.call_log.append("called")

        self.registry.add_action("test_hook", callback)
        assert self.registry.has_action("test_hook")

        result = self.registry.remove_action("test_hook", callback)

        assert result is True
        assert not self.registry.has_action("test_hook")

    def test_remove_action_nonexistent_hook(self):
        """Test removing from nonexistent hook returns False."""

        def callback() -> None:
            pass

        result = self.registry.remove_action("nonexistent", callback)

        assert result is False

    def test_remove_action_nonexistent_callback(self):
        """Test removing nonexistent callback returns False."""

        def callback1() -> None:
            pass

        def callback2() -> None:
            pass

        self.registry.add_action("test_hook", callback1)
        result = self.registry.remove_action("test_hook", callback2)

        assert result is False
        assert self.registry.has_action("test_hook")

    def test_remove_filter(self):
        """Test removing a filter callback."""

        def callback(x: str) -> str:
            return x

        self.registry.add_filter("test_filter", callback)
        assert self.registry.has_filter("test_filter")

        result = self.registry.remove_filter("test_filter", callback)

        assert result is True
        assert not self.registry.has_filter("test_filter")

    def test_remove_specific_callback_preserves_others(self):
        """Test that removing one callback preserves others."""

        def callback1() -> None:
            self.call_log.append("callback1")

        def callback2() -> None:
            self.call_log.append("callback2")

        self.registry.add_action("test_hook", callback1)
        self.registry.add_action("test_hook", callback2)

        self.registry.remove_action("test_hook", callback1)
        self.registry.do_action("test_hook")

        assert self.call_log == ["callback2"]


class TestHookRegistryInspection:
    """Test cases for hook inspection methods."""

    def setup_method(self):
        """Set up a fresh registry for each test."""
        self.registry = HookRegistry()

    def test_has_action_false_for_empty(self):
        """Test has_action returns False for empty registry."""
        assert not self.registry.has_action("test_hook")

    def test_has_action_true_after_registration(self):
        """Test has_action returns True after registration."""
        self.registry.add_action("test_hook", lambda: None)
        assert self.registry.has_action("test_hook")

    def test_has_action_false_after_removal(self):
        """Test has_action returns False after all callbacks removed."""

        def callback() -> None:
            pass

        self.registry.add_action("test_hook", callback)
        self.registry.remove_action("test_hook", callback)

        assert not self.registry.has_action("test_hook")

    def test_has_filter_false_for_empty(self):
        """Test has_filter returns False for empty registry."""
        assert not self.registry.has_filter("test_filter")

    def test_has_filter_true_after_registration(self):
        """Test has_filter returns True after registration."""
        self.registry.add_filter("test_filter", lambda x: x)
        assert self.registry.has_filter("test_filter")


class TestHookRegistryClear:
    """Test cases for clear() method."""

    def setup_method(self):
        """Set up a fresh registry for each test."""
        self.registry = HookRegistry()

    def test_clear_removes_all_actions(self):
        """Test that clear() removes all actions."""
        self.registry.add_action("hook1", lambda: None)
        self.registry.add_action("hook2", lambda: None)

        self.registry.clear()

        assert not self.registry.has_action("hook1")
        assert not self.registry.has_action("hook2")

    def test_clear_removes_all_filters(self):
        """Test that clear() removes all filters."""
        self.registry.add_filter("filter1", lambda x: x)
        self.registry.add_filter("filter2", lambda x: x)

        self.registry.clear()

        assert not self.registry.has_filter("filter1")
        assert not self.registry.has_filter("filter2")

    def test_clear_resets_callback_counter(self):
        """Test that clear() resets the callback counter."""
        self.registry.add_action("test_hook", lambda: None)
        initial_counter = self.registry._callback_counter

        self.registry.clear()

        assert self.registry._callback_counter == 0
        assert initial_counter > 0


class TestGlobalHookRegistry:
    """Test cases for the global hooks() singleton."""

    def teardown_method(self):
        """Clean up global registry after each test."""
        hooks().clear()

    def test_hooks_returns_singleton(self):
        """Test that hooks() returns the same instance."""
        registry1 = hooks()
        registry2 = hooks()

        assert registry1 is registry2
        assert isinstance(registry1, HookRegistry)

    def test_hooks_singleton_persistence(self):
        """Test that registrations persist across calls."""
        hooks().add_action("test_hook", lambda: None)

        assert hooks().has_action("test_hook")

    def test_hooks_state_isolation_from_local(self):
        """Test that global registry is separate from local instances."""
        global_registry = hooks()
        local_registry = HookRegistry()

        global_registry.add_action("global_hook", lambda: None)
        local_registry.add_action("local_hook", lambda: None)

        assert global_registry.has_action("global_hook")
        assert not global_registry.has_action("local_hook")
        assert local_registry.has_action("local_hook")
        assert not local_registry.has_action("global_hook")
