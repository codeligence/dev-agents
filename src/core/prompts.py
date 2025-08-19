import os
import threading
from pathlib import Path

from dotenv import load_dotenv
from dynaconf import Dynaconf

from core.log import get_logger

load_dotenv()

logger = get_logger("BasePrompts")


class BasePrompts:
    """Base prompts class that loads and resolves YAML prompts with environment variables using Dynaconf."""

    def __init__(self, prompts_path: str = None):
        if prompts_path is None:
            # Default to config/prompts.yaml relative to project root
            project_root = Path(__file__).parent.parent.parent
            prompts_path = project_root / "config" / "prompts.yaml"

        self._prompts_path = prompts_path
        self._settings = self._load_prompts()

    def _load_prompts(self) -> Dynaconf:
        """Load and resolve the YAML prompts file using Dynaconf."""
        if not os.path.exists(self._prompts_path):
            raise FileNotFoundError(f"Prompts file not found: {self._prompts_path}")

        # Use Dynaconf to load prompts with environment variable resolution
        settings = Dynaconf(
            settings_files=[str(self._prompts_path), str(self._prompts_path).replace(".yaml", ".custom.yaml")],
            envvar_prefix="",
            environments=False,
            load_dotenv=True,
            merge_enabled=True,
        )
        return settings

    def get_prompt(self, key_path: str, default: str = None) -> str:
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
            return self._settings.get(key_path, default)
        except Exception as e:
            logger.warning(f"Error Prompt key '{key_path}' not found: {str(e)}")
            return default


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
