from pathlib import Path
from typing import Any
import threading

from dynaconf import Dynaconf

from core.log import get_logger

logger = get_logger("BasePrompts")

# Re-use the same bundled defaults directory as BaseConfig
_BUNDLED_PROMPTS_DIR = Path(__file__).parent / "defaults"


class BasePrompts:
    """Base prompts class that loads and resolves YAML prompts with environment variables using Dynaconf.

    Uses the same layered resolution strategy as :class:`BaseConfig`:

    1. **Bundled defaults** (``core/defaults/prompts.yaml``) — ships with
       the package.
    2. **CWD override** (``<cwd>/config/prompts.yaml``) — if present,
       *replaces* the bundled defaults entirely.
    3. **CWD custom overlay** (``<cwd>/config/prompts.custom.yaml``) — if
       present, merged on top.
    """

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
            if prompts_path is not None:
                # Explicit path: load just that file + its .custom variant
                self._prompts_path = prompts_path
                self._settings = self._load_prompts()
            else:
                # Default: layered resolution (same pattern as BaseConfig)
                self._prompts_path, self._settings = self._load_layered_prompts(
                    "prompts.yaml"
                )

    @staticmethod
    def _load_layered_prompts(filename: str) -> tuple[str, "Dynaconf"]:
        """Load prompts using layered resolution: bundled → CWD replace → CWD custom.

        Args:
            filename: Base filename (e.g. ``prompts.yaml``).

        Returns:
            Tuple of (resolved primary path, loaded Dynaconf settings).
        """
        custom_filename = filename.replace(".yaml", ".custom.yaml")
        settings_files: list[str] = []

        # Determine base prompts: CWD replaces bundled if present
        cwd_prompts = Path.cwd() / "config" / filename
        bundled_prompts = _BUNDLED_PROMPTS_DIR / filename

        if cwd_prompts.is_file():
            primary_path = str(cwd_prompts)
            settings_files.append(primary_path)
            logger.info(f"Using CWD prompts: {cwd_prompts}")
        elif bundled_prompts.is_file():
            primary_path = str(bundled_prompts)
            settings_files.append(primary_path)
            logger.info(f"Using bundled prompts: {bundled_prompts}")
        else:
            raise FileNotFoundError(
                f"No {filename} found. Searched:\n"
                f"  - {cwd_prompts}\n"
                f"  - {bundled_prompts}\n"
                "Place a prompts file in <project>/config/ or install the package "
                "with bundled defaults."
            )

        # Custom overlay merges on top
        cwd_custom = Path.cwd() / "config" / custom_filename
        if cwd_custom.is_file():
            settings_files.append(str(cwd_custom))
            logger.info(f"Merging custom overlay: {cwd_custom}")

        settings = Dynaconf(
            settings_files=settings_files,
            envvar_prefix="",
            envvar_default="",
            ignore_unknown_envvars=True,
            environments=False,
            env_switcher="DYNACONF_ENV",
            load_dotenv=False,
            merge_enabled=True,
        )
        return primary_path, settings

    def _load_prompts(self) -> Dynaconf:
        """Load prompts from an explicit path (+ its .custom variant)."""
        assert self._prompts_path is not None
        if not Path(self._prompts_path).exists():
            raise FileNotFoundError(f"Prompts file not found: {self._prompts_path}")

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
