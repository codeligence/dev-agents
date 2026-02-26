"""Version update check functionality."""

from typing import Any

import httpx

from core.config import get_default_config
from core.log import get_logger

# Version is managed by commitizen and kept in sync with pyproject.toml
__version__ = "1.0.0"

logger = get_logger("VersionCheck")


async def check_for_updates() -> None:
    """Check for available updates from version check service.

    Performs a non-blocking check to see if a newer version is available.
    If configured URL is empty, skips the check silently.
    Logs prominent INFO message when update is available.
    All errors are handled gracefully and logged at DEBUG level.
    """
    try:
        # Get version check URL from configuration
        config = get_default_config()
        version_check_url = config.get_value("core.version_check_url")

        # Skip if not configured
        if not version_check_url:
            logger.debug("Version update check skipped (not configured)")
            return

        # Make POST request with current version
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                version_check_url,
                json={"version": __version__},
                headers={"Content-Type": "application/json"},
            )

            response.raise_for_status()
            data: dict[str, Any] = response.json()

            # Check if update is available
            if data.get("update") is True:
                new_version = data.get("version", "unknown")
                logger.info(
                    f"🔔 UPDATE AVAILABLE: Version {new_version} is available "
                    f"(current: {__version__})"
                )
            else:
                logger.debug(f"Version {__version__} is up to date")

    except httpx.TimeoutException:
        logger.debug("Version check timed out (non-critical)")
    except httpx.HTTPStatusError as e:
        logger.debug(f"Version check HTTP error: {e.response.status_code}")
    except httpx.RequestError as e:
        logger.debug(f"Version check request failed: {e}")
    except Exception as e:
        logger.debug(f"Version check failed: {e}")
