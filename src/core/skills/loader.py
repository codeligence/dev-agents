"""Config-driven skill loading.

Reads the ``skills.enable`` list from configuration and imports each module,
calling its ``setup()`` function so that skills can register their tools via
the hook system.  Short names like ``"test_plan"`` are resolved to
``"skills.test_plan"`` automatically.  Fully-qualified names (containing a dot)
are used as-is, supporting external library skills
(e.g. ``acme_devtools.skills.lint_check``).
"""

import importlib

from core.log import get_logger

logger = get_logger("SkillLoader")

_loaded = False


def load_skills() -> list[str]:
    """Load skill modules listed in the ``skills.enable`` configuration.

    Each module must expose a module-level ``setup()`` function.
    The function is called once during loading so the skill can register
    its hooks (e.g. ``gitchatbot.register_tools``).

    This function is idempotent — calling it multiple times has no effect
    after the first successful invocation.

    Returns:
        List of loaded skill module names.
    """
    global _loaded  # noqa: PLW0603
    if _loaded:
        logger.debug("Skills already loaded, skipping")
        return []

    from core.config import get_default_config

    config = get_default_config()
    skill_modules: list[str] = config.get_value("skills.enable", [])

    if not skill_modules:
        logger.info("No skills configured in skills.enable")
        _loaded = True
        return []

    loaded_names: list[str] = []

    for raw_name in skill_modules:
        module_name = raw_name if "." in raw_name else f"skills.{raw_name}"
        try:
            module = importlib.import_module(module_name)
        except Exception:
            logger.exception(f"Failed to import skill module '{module_name}'")
            continue

        setup_fn = getattr(module, "setup", None)
        if setup_fn is None:
            logger.warning(f"Skill module '{module_name}' has no setup() — skipping")
            continue

        try:
            setup_fn()
            loaded_names.append(module_name)
            logger.info(f"Loaded skill: {module_name}")
        except Exception:
            logger.exception(f"Error in setup() for skill '{module_name}'")

    _loaded = True
    logger.info(
        f"Skill loading complete. Loaded {len(loaded_names)} skill(s): {loaded_names}"
    )
    return loaded_names
