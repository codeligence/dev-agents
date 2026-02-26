"""Skills subsystem — public API.

Call ``load_skills()`` early in application startup (before any agent runs)
to discover and register all skill modules via the hook system.
"""

from core.skills.loader import load_skills

__all__ = ["load_skills"]
