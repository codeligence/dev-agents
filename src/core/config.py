from pathlib import Path
from typing import Any, Optional, cast
import os
import threading

from dotenv import load_dotenv
from dynaconf import Dynaconf
import yaml

from core.exceptions import ConfigurationError
from core.log import get_logger
from core.project_config import ProjectConfig

load_dotenv()
logger = get_logger("BaseConfig")

# Bundled defaults ship inside the package
_BUNDLED_CONFIG_DIR = Path(__file__).parent / "defaults"

# Sections that represent user-defined entities (not config templates).
# When a custom overlay redefines one of these sections, bundled-only keys
# are pruned so placeholder entries don't pollute the user's entity list.
_ENTITY_SECTIONS = ("projects",)


def _prune_bundled_entity_keys(
    settings: Dynaconf,
    bundled_path: str,
    custom_path: str,
) -> None:
    """Remove bundled-only keys from entity sections that the custom overlay redefines.

    When a custom overlay defines entries in an entity section (e.g. ``projects``),
    Dynaconf's deep merge retains all keys from the bundled defaults.  This function
    removes keys that exist only in the bundled defaults — not in the custom overlay —
    so the user's entity list is not polluted with placeholder entries.

    Only operates on sections listed in :data:`_ENTITY_SECTIONS`.

    Args:
        settings: The already-loaded Dynaconf instance (mutated in place).
        bundled_path: Path to the bundled defaults YAML file.
        custom_path: Path to the custom overlay YAML file.
    """
    with Path(bundled_path).open() as f:
        bundled_raw: dict[str, Any] = yaml.safe_load(f) or {}
    with Path(custom_path).open() as f:
        custom_raw: dict[str, Any] = yaml.safe_load(f) or {}

    for section in _ENTITY_SECTIONS:
        custom_section = custom_raw.get(section)
        bundled_section = bundled_raw.get(section)

        # Only prune when both files define the section as dicts
        if not isinstance(custom_section, dict) or not isinstance(
            bundled_section, dict
        ):
            continue

        # Keys present in bundled but absent from custom overlay
        bundled_only = set(bundled_section.keys()) - set(custom_section.keys())
        if not bundled_only:
            continue

        merged_section = settings.get(section)
        if not isinstance(merged_section, dict):
            continue

        for key in bundled_only:
            if key in merged_section:
                del merged_section[key]
                logger.info(
                    f"Pruned bundled-only key '{section}.{key}' "
                    f"(not defined in custom overlay)"
                )

        settings.set(section, merged_section)


class BaseConfig:
    """Base configuration class that loads and resolves YAML config with environment variables using Dynaconf.

    When no explicit ``config_path`` is provided, config files are resolved
    using a layered strategy:

    1. **Bundled defaults** (``core/defaults/config.yaml``) — always available,
       ships with the package.
    2. **CWD override** (``<cwd>/config/config.yaml``) — if present, *replaces*
       the bundled defaults entirely.
    3. **CWD custom overlay** (``<cwd>/config/config.custom.yaml``) — if present,
       merged on top of whichever base was chosen above.

    This ensures the package works out-of-the-box when installed via PyPI,
    while allowing full customization when run from a project directory
    or Docker image.
    """

    _config_path: str
    _settings: Any
    _config_data: dict[str, Any]

    def __init__(
        self,
        config_path: str | None = None,
        base_config: Optional["BaseConfig"] = None,
    ):
        if base_config is not None:
            # Copy constructor: copy fields from another BaseConfig instance
            self._config_path = base_config._config_path
            self._settings = base_config._settings
            self._config_data = base_config._config_data
        else:
            if config_path is not None:
                # Explicit path: load just that file + its .custom variant
                self._config_path = config_path
                self._settings = self._load_config()
            else:
                # Default: layered resolution
                self._config_path, self._settings = self._load_layered_config(
                    "config.yaml"
                )

            # Keep backward compatibility for tests
            try:
                self._config_data = self._settings.to_dict()
            except Exception as e:
                logger.exception(f"Failed to load config: {e}")
                # Fallback to basic dict if to_dict() fails
                self._config_data = {}

    @staticmethod
    def _load_layered_config(filename: str) -> tuple[str, "Dynaconf"]:
        """Load config using layered resolution: bundled → CWD replace → CWD custom.

        Args:
            filename: Base filename (e.g. ``config.yaml``).

        Returns:
            Tuple of (resolved primary path, loaded Dynaconf settings).
        """
        custom_filename = filename.replace(".yaml", ".custom.yaml")
        settings_files: list[str] = []

        # Determine base config: CWD replaces bundled if present
        cwd_config = Path.cwd() / "config" / filename
        bundled_config = _BUNDLED_CONFIG_DIR / filename
        used_bundled = False

        if cwd_config.is_file():
            primary_path = str(cwd_config)
            settings_files.append(primary_path)
            logger.info(f"Using CWD config: {cwd_config}")
        elif bundled_config.is_file():
            primary_path = str(bundled_config)
            settings_files.append(primary_path)
            used_bundled = True
            logger.info(f"Using bundled config: {bundled_config}")
        else:
            raise FileNotFoundError(
                f"No {filename} found. Searched:\n"
                f"  - {cwd_config}\n"
                f"  - {bundled_config}\n"
                "Place a config file in <project>/config/ or install the package "
                "with bundled defaults."
            )

        # Custom overlay merges on top
        cwd_custom = Path.cwd() / "config" / custom_filename
        custom_path: str | None = None
        if cwd_custom.is_file():
            custom_path = str(cwd_custom)
            settings_files.append(custom_path)
            logger.info(f"Merging custom overlay: {cwd_custom}")

        settings = Dynaconf(
            settings_files=settings_files,
            envvar_prefix="",
            envvar_default="",
            ignore_unknown_envvars=True,
            environments=False,
            load_dotenv=False,
            env_switcher="DYNACONF_ENV",
            merge_enabled=True,
            auto_cast=True,
        )

        # Prune bundled-only entity keys when custom overlay redefines sections
        if used_bundled and custom_path:
            _prune_bundled_entity_keys(settings, str(bundled_config), custom_path)

        return primary_path, settings

    def _load_config(self) -> Dynaconf:
        """Load config from an explicit path (+ its .custom variant)."""
        if not Path(self._config_path).exists():
            raise FileNotFoundError(f"Config file not found: {self._config_path}")

        settings = Dynaconf(
            settings_files=[
                str(self._config_path),
                str(self._config_path).replace(".yaml", ".custom.yaml"),
            ],
            envvar_prefix="",
            envvar_default="",
            ignore_unknown_envvars=True,
            environments=False,
            load_dotenv=False,
            env_switcher="DYNACONF_ENV",
            merge_enabled=True,
            auto_cast=True,
        )
        return settings

    def get_config_data(self) -> dict[str, Any]:
        """Get the full resolved configuration data."""
        try:
            return cast("dict[str, Any]", self._settings.to_dict())
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
            env_key = key_path.replace(".", "_").upper()
            env_value = os.getenv(env_key)
            if env_value is not None:
                return env_value

            # Try Dynaconf's double underscore format
            dynaconf_key = key_path.replace(".", "__").upper()
            dynaconf_value = os.getenv(dynaconf_key)
            if dynaconf_value is not None:
                return dynaconf_value

            return default
        except Exception:
            return default

    def get_available_projects(self) -> list[str]:
        """Get list of configured project names."""
        projects = self.get_value("projects", {})
        return list(projects.keys())

    def get_project_config(self, project_name: str) -> ProjectConfig:
        """Get configuration for a specific project.

        Args:
            project_name: Name of the project

        Returns:
            ProjectConfig instance

        Raises:
            ConfigurationError: If project is not found
        """
        projects = self.get_value("projects", {})
        if project_name not in projects:
            available = ", ".join(self.get_available_projects())
            raise ConfigurationError(
                f"Project '{project_name}' not found in configuration. "
                f"Available projects: {available}"
            )

        return ProjectConfig(project_name, self)

    def get_default_project_config(self) -> ProjectConfig:
        """Get the default project configuration."""
        return self.get_project_config("default")

    def with_overlay(self, overlay_path: str) -> "BaseConfig":
        """Create a new config with overlay merged on top of this one.

        Clones the current settings in memory (no disk I/O for the base)
        and merges the overlay file on top of the clone.

        Args:
            overlay_path: Path to the overlay YAML file to merge.

        Returns:
            New BaseConfig instance with overlay values merged.
        """
        clone = object.__new__(type(self))
        clone._config_path = self._config_path
        clone._settings = self._settings.dynaconf_clone()
        clone._config_data = {}
        if Path(overlay_path).exists():
            clone._settings.load_file(path=overlay_path)
        return clone


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
