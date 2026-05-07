from collections import OrderedDict
from unittest.mock import patch
import asyncio

import pytest

from entrypoints.slack_entrypoint.slack_bot_runtime import (
    _TITLED_THREADS_MAX,
    SlackBotRuntime,
)


@pytest.fixture
def runtime() -> SlackBotRuntime:
    """Build a runtime without booting Bolt's ``AsyncApp``.

    Memory-management helpers (``_hold_thread_lock`` and
    ``_remember_titled_thread``) are pure data-structure operations that
    don't need the network stack, so we bypass ``__init__`` and only set
    the attributes they touch.
    """
    with patch.object(SlackBotRuntime, "__init__", lambda _self: None):
        rt = SlackBotRuntime()  # type: ignore[call-arg]
        rt.thread_locks = {}
        rt._thread_lock_refs = {}
        rt.main_lock = asyncio.Lock()
        rt._titled_assistant_threads = OrderedDict()
        return rt


class TestHoldThreadLockRefcount:
    """``_hold_thread_lock`` must drop entries after the last waiter exits.

    Otherwise ``thread_locks`` grows unboundedly with thread cardinality.
    """

    @pytest.mark.asyncio
    async def test_lock_removed_after_release(self, runtime: SlackBotRuntime) -> None:
        async with runtime._hold_thread_lock("T1"):
            assert "T1" in runtime.thread_locks
            assert runtime._thread_lock_refs["T1"] == 1
        assert runtime.thread_locks == {}
        assert runtime._thread_lock_refs == {}

    @pytest.mark.asyncio
    async def test_concurrent_waiters_share_lock_then_cleanup(
        self, runtime: SlackBotRuntime
    ) -> None:
        order: list[str] = []
        gate = asyncio.Event()

        async def worker(name: str) -> None:
            async with runtime._hold_thread_lock("T1"):
                order.append(f"{name}-enter")
                await gate.wait()
                order.append(f"{name}-exit")

        task_a = asyncio.create_task(worker("A"))
        await asyncio.sleep(0)
        task_b = asyncio.create_task(worker("B"))
        await asyncio.sleep(0)

        assert runtime._thread_lock_refs["T1"] == 2

        gate.set()
        await asyncio.gather(task_a, task_b)

        assert order[0].endswith("-enter") and order[1].endswith("-exit")
        assert runtime.thread_locks == {}
        assert runtime._thread_lock_refs == {}

    @pytest.mark.asyncio
    async def test_independent_threads_independent_locks(
        self, runtime: SlackBotRuntime
    ) -> None:
        async with runtime._hold_thread_lock("T1"):
            async with runtime._hold_thread_lock("T2"):
                assert set(runtime.thread_locks) == {"T1", "T2"}
                assert runtime._thread_lock_refs == {"T1": 1, "T2": 1}
            assert "T2" not in runtime.thread_locks
            assert "T1" in runtime.thread_locks
        assert runtime.thread_locks == {}

    @pytest.mark.asyncio
    async def test_exception_inside_block_still_releases(
        self, runtime: SlackBotRuntime
    ) -> None:
        with pytest.raises(RuntimeError):
            async with runtime._hold_thread_lock("T1"):
                raise RuntimeError("boom")
        assert runtime.thread_locks == {}
        assert runtime._thread_lock_refs == {}


class TestRememberTitledThreadLru:
    """``_remember_titled_thread`` must bound memory via LRU eviction."""

    def test_first_seen_returns_true(self, runtime: SlackBotRuntime) -> None:
        assert runtime._remember_titled_thread("T1") is True

    def test_repeated_thread_returns_false_and_promotes(
        self, runtime: SlackBotRuntime
    ) -> None:
        runtime._remember_titled_thread("T1")
        runtime._remember_titled_thread("T2")
        assert runtime._remember_titled_thread("T1") is False
        # T1 was just touched, so it must be most-recent.
        assert next(reversed(runtime._titled_assistant_threads)) == "T1"

    def test_lru_evicts_oldest_at_cap(self, runtime: SlackBotRuntime) -> None:
        # Fill to the cap with synthetic ids.
        for i in range(_TITLED_THREADS_MAX):
            runtime._remember_titled_thread(f"T{i}")
        assert len(runtime._titled_assistant_threads) == _TITLED_THREADS_MAX

        # One more entry must evict the oldest, keeping size at the cap.
        runtime._remember_titled_thread("OVERFLOW")
        assert len(runtime._titled_assistant_threads) == _TITLED_THREADS_MAX
        assert "T0" not in runtime._titled_assistant_threads
        assert "OVERFLOW" in runtime._titled_assistant_threads

    def test_recent_use_protects_from_eviction(self, runtime: SlackBotRuntime) -> None:
        for i in range(_TITLED_THREADS_MAX):
            runtime._remember_titled_thread(f"T{i}")
        # Touch the oldest so it becomes most-recent.
        runtime._remember_titled_thread("T0")
        runtime._remember_titled_thread("OVERFLOW")
        assert "T0" in runtime._titled_assistant_threads
        assert "T1" not in runtime._titled_assistant_threads
