from collections.abc import Coroutine
from dataclasses import dataclass, field
from typing import Any
import asyncio
import logging

from core.log import get_logger


@dataclass
class ThreadTaskManager:
    """Manages asyncio tasks per Slack thread with cancellation support."""

    _tasks: dict[str, asyncio.Task[None]] = field(default_factory=dict)
    _logger: logging.Logger = field(
        default_factory=lambda: get_logger("ThreadTaskManager")
    )

    def start_task(
        self,
        thread_id: str,
        coro: Coroutine[Any, Any, None],
    ) -> asyncio.Task[None]:
        """Create and track a task for a thread.

        Args:
            thread_id: The Slack thread identifier.
            coro: The coroutine to execute.

        Returns:
            The created asyncio Task.
        """
        task = asyncio.create_task(coro)
        self._tasks[thread_id] = task
        task.add_done_callback(lambda _: self._cleanup(thread_id))
        return task

    def cancel_task(self, thread_id: str) -> bool:
        """Cancel task if running.

        Args:
            thread_id: The Slack thread identifier.

        Returns:
            True if task was cancelled, False otherwise.
        """
        task = self._tasks.get(thread_id)
        if task and not task.done():
            self._logger.info(f"Cancelling task for thread {thread_id}")
            task.cancel()
            return True
        elif task and task.done():
            self._logger.info(
                f"Task for thread {thread_id} already done, cannot cancel"
            )
        else:
            self._logger.warning(
                f"No task found for thread {thread_id}, "
                f"active tasks: {list(self._tasks.keys())}"
            )
        return False

    def is_active(self, thread_id: str) -> bool:
        """Check if a task is running for this thread.

        Args:
            thread_id: The Slack thread identifier.

        Returns:
            True if task is active, False otherwise.
        """
        task = self._tasks.get(thread_id)
        return task is not None and not task.done()

    def _cleanup(self, thread_id: str) -> None:
        """Remove task reference after completion.

        Args:
            thread_id: The Slack thread identifier.
        """
        self._tasks.pop(thread_id, None)
