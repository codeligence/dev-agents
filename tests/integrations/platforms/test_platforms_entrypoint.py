"""Tests for the platforms entrypoint service."""

from unittest.mock import AsyncMock, MagicMock, patch
import threading

import pytest


class TestPlatformsEntrypoint:
    @pytest.mark.asyncio
    async def test_run_starts_and_stops_platforms(self):
        """Verify _run() calls start_platforms then stop_platforms on shutdown."""
        mock_start = AsyncMock()
        mock_stop = AsyncMock()

        shutdown_event = threading.Event()
        # Set immediately so _run doesn't block
        shutdown_event.set()

        with (
            patch("integrations.platforms.start_platforms", mock_start),
            patch("integrations.platforms.stop_platforms", mock_stop),
            patch("entrypoints.platforms_entrypoint.service._register_agents"),
        ):
            from entrypoints.platforms_entrypoint.service import _run

            await _run(shutdown_event)

        mock_start.assert_called_once()
        mock_stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_registers_agents(self):
        """Verify _run() creates an AgentService and registers agents."""
        shutdown_event = threading.Event()
        shutdown_event.set()

        mock_agent_service = MagicMock()

        with (
            patch("integrations.platforms.start_platforms", AsyncMock()),
            patch("integrations.platforms.stop_platforms", AsyncMock()),
            patch(
                "entrypoints.platforms_entrypoint.service.AgentService",
                return_value=mock_agent_service,
            ),
            patch(
                "entrypoints.platforms_entrypoint.service._register_agents"
            ) as mock_register,
        ):
            from entrypoints.platforms_entrypoint.service import _run

            await _run(shutdown_event)

        mock_register.assert_called_once_with(mock_agent_service)
