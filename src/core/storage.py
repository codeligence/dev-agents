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


from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
import json

from core.config import BaseConfig, get_default_config
from core.log import get_logger


class BaseStorage(ABC):
    """Abstract base class for storage implementations."""

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a value from storage.

        Args:
            key: The key to retrieve
            default: Default value if key doesn't exist

        Returns:
            The stored value or default
        """
        pass

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """
        Store a value in storage.

        Args:
            key: The key to store under
            value: The value to store
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """
        Delete a key from storage.

        Args:
            key: The key to delete

        Returns:
            True if deleted, False if key didn't exist
        """
        pass


class FileStorage(BaseStorage):
    """File-based storage implementation using JSON files."""

    def __init__(self, base_config: BaseConfig | None = None):
        """
        Initialize FileStorage with configuration.

        Args:
            base_config: Base configuration object
        """
        self._base_config = base_config or get_default_config()
        self.logger = get_logger("FileStorage")

        # Get storage directory from config
        storage_dir = self._base_config.get_value("core.storage.file.dir", "./storage")
        self.storage_dir = Path(storage_dir)

        # Ensure storage directory exists
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"File storage directory: {self.storage_dir}")

    def _get_file_path(self, key: str) -> Path:
        """Get file path for a given key."""
        return self.storage_dir / f"{key}.json"

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a value from file storage.

        Args:
            key: The key to retrieve
            default: Default value if key doesn't exist

        Returns:
            The stored value or default
        """
        try:
            file_path = self._get_file_path(key)

            if not file_path.exists():
                self.logger.debug(f"No stored file found for key '{key}'")
                return default

            with Path(file_path).open() as f:
                value = json.load(f)

            self.logger.debug(f"Retrieved value for key '{key}' from {file_path}")
            return value

        except Exception as e:
            self.logger.error(f"Error retrieving value for key '{key}': {str(e)}")
            return default

    def set(self, key: str, value: Any) -> None:
        """
        Store a value in file storage.

        Args:
            key: The key to store under
            value: The value to store (must be JSON serializable)
        """
        try:
            file_path = self._get_file_path(key)

            with Path(file_path).open("w") as f:
                json.dump(value, f, indent=2)

            self.logger.debug(f"Stored value for key '{key}' at {file_path}")

        except Exception as e:
            self.logger.error(f"Error storing value for key '{key}': {str(e)}")

    def delete(self, key: str) -> bool:
        """
        Delete a key from file storage.

        Args:
            key: The key to delete

        Returns:
            True if deleted, False if key didn't exist
        """
        try:
            file_path = self._get_file_path(key)

            if file_path.exists():
                file_path.unlink()
                self.logger.debug(f"Deleted file for key '{key}'")
                return True

            return False

        except Exception as e:
            self.logger.error(f"Error deleting key '{key}': {str(e)}")
            return False


# Global storage cache - similar to logger cache pattern
_storage_cache: dict[str, BaseStorage] = {}


def get_storage(config: BaseConfig | None = None) -> BaseStorage:
    """
    Get a global storage instance based on configuration.

    Uses a singleton pattern to avoid multiple storage instances with the same configuration.
    Automatically detects storage type from configuration:
    - If core.storage.file.dir is configured -> FileStorage
    - Future: Redis, Database, etc.

    Args:
        config: Optional BaseConfig instance. If None, creates a new one.

    Returns:
        BaseStorage instance configured based on settings
    """
    # Use default config if none provided
    if config is None:
        config = get_default_config()

    # Create cache key based on config values
    storage_file_dir = config.get_value("core.storage.file.dir")
    cache_key = f"file:{storage_file_dir}" if storage_file_dir else "default"

    # Return cached instance if available
    if cache_key in _storage_cache:
        return _storage_cache[cache_key]

    # Create new storage instance based on configuration
    storage_instance = _create_storage_instance(config)

    # Cache the instance
    _storage_cache[cache_key] = storage_instance

    logger = get_logger("GlobalStorage")
    logger.info(
        f"Created global storage instance: {type(storage_instance).__name__} (cache_key: {cache_key})"
    )

    return storage_instance


def _create_storage_instance(config: BaseConfig) -> BaseStorage:
    """
    Create a storage instance based on configuration.

    Args:
        config: BaseConfig instance

    Returns:
        BaseStorage instance
    """
    # Check for file storage configuration
    storage_file_dir = config.get_value("core.storage.file.dir")
    if storage_file_dir:
        return FileStorage(config)

    # Future: Add other storage types here

    # Default fallback to file storage
    return FileStorage(config)
