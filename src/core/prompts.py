from pathlib import Path
from typing import Any
import threading

from dotenv import load_dotenv
from dynaconf import Dynaconf

from core.log import get_logger

load_dotenv()

logger = get_logger("BasePrompts")


class BasePrompts:
    """Base prompts class that loads and resolves YAML prompts with environment variables using Dynaconf."""

    _prompts_path: str
    _settings: Any

    def __init__(
        self,
        prompts_path: str | None = None,
        base_prompts: "BasePrompts | None" = None,
    ):
        if base_prompts is not None:
            # Copy constructor: share settings from another BasePrompts instance
            self._prompts_path = base_prompts._prompts_path
            self._settings = base_prompts._settings
        else:
            if prompts_path is None:
                # Default to config/prompts.yaml relative to project root
                project_root = Path(__file__).parent.parent.parent
                prompts_path = str(project_root / "config" / "prompts.yaml")

            self._prompts_path = prompts_path
            self._settings = self._load_prompts()

    def _load_prompts(self) -> Dynaconf:
        """Load and resolve the YAML prompts file using Dynaconf."""
        assert self._prompts_path is not None
        if not Path(self._prompts_path).exists():
            raise FileNotFoundError(f"Prompts file not found: {self._prompts_path}")

        # Use Dynaconf to load prompts with environment variable resolution
        settings = Dynaconf(
            settings_files=[
                str(self._prompts_path),
                str(self._prompts_path).replace(".yaml", ".custom.yaml"),
            ],
            envvar_prefix="",
            envvar_default="",
            ignore_unknown_envvars=True,
            environments=False,
            env_switcher="DYNACONF_ENV",
            load_dotenv=False,
            merge_enabled=True,
        )
        return settings

    def get_prompt(self, key_path: str, default: str = "") -> str:
        """
        Get a prompt from the prompts using dot notation.

        Args:
            key_path: Dot-separated path to the prompt (e.g., 'agents.chatbot.initial')
            default: Default value if key is not found

        Returns:
            The prompt string or default
        """
        try:
            # Dynaconf supports dot notation natively
            result = self._settings.get(key_path, default)
            return str(result) if result is not None else default
        except Exception as e:
            logger.warning(f"Error Prompt key '{key_path}' not found: {str(e)}")
            return default

    def with_overlay(self, overlay_path: str) -> "BasePrompts":
        """Create a new prompts instance with overlay merged on top of this one.

        Clones the current settings in memory (no disk I/O for the base)
        and merges the overlay file on top of the clone.

        Args:
            overlay_path: Path to the overlay YAML file to merge.

        Returns:
            New BasePrompts instance with overlay values merged.
        """
        clone = object.__new__(type(self))
        clone._prompts_path = self._prompts_path
        clone._settings = self._settings.dynaconf_clone()
        if Path(overlay_path).exists():
            clone._settings.load_file(path=overlay_path)
        return clone


# Global default prompts instance - thread-safe singleton
_default_prompts_instance = None
_default_prompts_lock = threading.Lock()


def get_default_prompts() -> BasePrompts:
    """
    Get the global default prompts instance.

    Uses singleton pattern with single cached instance for the default prompts.yaml.
    This covers 99% of use cases where only the default prompts are needed.
    Thread-safe implementation using double-checked locking pattern.

    Returns:
        BasePrompts instance loaded from default prompts.yaml
    """
    global _default_prompts_instance

    # First check without lock for performance
    if _default_prompts_instance is None:
        with _default_prompts_lock:
            # Double-checked locking pattern
            if _default_prompts_instance is None:
                logger.info("Creating global default prompts instance")
                _default_prompts_instance = BasePrompts()

    return _default_prompts_instance
