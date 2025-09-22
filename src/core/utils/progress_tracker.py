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

"""
A reusable progress tracking utility that manages file processing progress
and reports status updates via a callback function.
"""

from collections.abc import Awaitable, Callable
import asyncio


class ProgressTracker:
    """
    A reusable progress tracking utility that manages file processing progress
    and reports status updates via a callback function.
    """

    def __init__(
        self,
        status_callback: (
            Callable[[str], None] | Callable[[str], Awaitable[None]] | None
        ) = None,
    ):
        """
        Initialize the ProgressTracker.

        Args:
            status_callback: Optional callback function to call with progress updates
        """
        self.status_callback = status_callback
        self.total = 0
        self.current = 0

    def reset(self, total: int) -> None:
        """
        Reset the progress tracker with a new total count.

        Args:
            total: Total number of items to process
        """
        self.total = max(0, total)
        self.current = 0

    def update(self) -> None:
        """
        Increment the progress counter and report status if callback is available.
        Calculates percentage and calls the status callback with the current progress.
        """
        if self.status_callback and self.total > 0:
            percentage = int((self.current / self.total) * 100)
            result = self.status_callback(f"📂 {percentage}%")
            # If the callback returns an awaitable, run it in the event loop if possible
            if asyncio.iscoroutine(result):
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # Schedule the coroutine to run soon
                        loop.create_task(result)
                    else:
                        # Run it directly if no loop is running
                        loop.run_until_complete(result)
                except RuntimeError:
                    # If we can't get a loop, ignore the progress update
                    pass

        self.current += 1

    def get_percentage(self) -> int:
        """
        Get the current progress percentage.

        Returns:
            Progress percentage as integer (0-100)
        """
        if self.total == 0:
            return 0
        return int((self.current / self.total) * 100)

    async def async_update(self) -> None:
        """
        Async version of update() for use in async contexts.
        Increment the progress counter and report status if callback is available.
        """
        if self.status_callback and self.total > 0:
            percentage = int((self.current / self.total) * 100)
            result = self.status_callback(f"📂 {percentage}%")
            # If the callback returns an awaitable, await it
            if asyncio.iscoroutine(result):
                await result

        self.current += 1
