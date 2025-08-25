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


from typing import Dict, Any
import os
import threading
from pathlib import Path

from dotenv import load_dotenv
from dynaconf import Dynaconf

from core.log import get_logger

load_dotenv()
logger = get_logger("BaseConfig")


class BaseConfig:
    """Base configuration class that loads and resolves YAML config with environment variables using Dynaconf."""

    def __init__(self, config_path: str = None, base_config: 'BaseConfig' = None):
        if base_config is not None:
            # Copy constructor: copy fields from another BaseConfig instance
            self._config_path = base_config._config_path
            self._settings = base_config._settings
            self._config_data = base_config._config_data
        else:
            # Normal constructor: load config from path
            if config_path is None:
                # Default to config/config.yml relative to project root
                project_root = Path(__file__).parent.parent.parent
                config_path = project_root / "config" / "config.yaml"

            self._config_path = config_path
            self._settings = self._load_config()
            # Keep backward compatibility for tests
            try:
                self._config_data = self._settings.to_dict()
            except Exception as e:
                logger.exception("Failed to load config: {}".format(e))
                # Fallback to basic dict if to_dict() fails
                self._config_data = {}

    def _load_config(self) -> Dynaconf:
        """Load and resolve the YAML configuration file using Dynaconf."""
        if not os.path.exists(self._config_path):
            raise FileNotFoundError(f"Config file not found: {self._config_path}")

        # Use Dynaconf to load config with environment variable resolution
        settings = Dynaconf(
            settings_files=[str(self._config_path), str(self._config_path).replace(".yaml", ".custom.yaml")],
            envvar_prefix="",  # Allow all environment variables
            envvar_default="",
            ignore_unknown_envvars=True,
            environments=False,
            load_dotenv=True,
            # Set up environment variable resolution for nested keys
            env_switcher="DYNACONF_ENV",
            merge_enabled=True,
            # Enable auto-casting for environment variables
            auto_cast=True,
        )
        return settings

    def get_config_data(self) -> Dict[str, Any]:
        """Get the full resolved configuration data."""
        try:
            return self._settings.to_dict()
        except Exception:
            # Fallback to cached data if to_dict() fails
            return self._config_data

    def get_value(self, key_path: str, default: Any = None) -> Any:
        """
        Get a value from the config using dot notation.

        Args:
            key_path: Dot-separated path to the config value (e.g., 'azure.devops.pat')
            default: Default value if key is not found

        Returns:
            The configuration value or default
        """
        try:
            # First try Dynaconf's dot notation
            value = self._settings.get(key_path, None)
            if value is not None:
                return value

            # If not found, try environment variables
            # Convert dot notation to environment variable format
            env_key = key_path.replace('.', '_').upper()
            env_value = os.getenv(env_key)
            if env_value is not None:
                return env_value

            # Try Dynaconf's double underscore format
            dynaconf_key = key_path.replace('.', '__').upper()
            dynaconf_value = os.getenv(dynaconf_key)
            if dynaconf_value is not None:
                return dynaconf_value

            return default
        except Exception:
            return default


# Global default config instance - thread-safe singleton
_default_config_instance = None
_default_config_lock = threading.Lock()


def get_default_config() -> BaseConfig:
    """
    Get the global default configuration instance.

    Uses singleton pattern with single cached instance for the default config.yaml.
    This covers 99% of use cases where only the default configuration is needed.
    Thread-safe implementation using double-checked locking pattern.

    Returns:
        BaseConfig instance loaded from default config.yaml
    """
    global _default_config_instance

    # First check without lock for performance
    if _default_config_instance is None:
        with _default_config_lock:
            # Double-checked locking pattern
            if _default_config_instance is None:
                logger.info("Creating global default configuration instance")
                _default_config_instance = BaseConfig()

    return _default_config_instance
