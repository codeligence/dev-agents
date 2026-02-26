"""Dev Agents - AI Agents for Agile Dev Teams.

This package provides AI agents for common development workflow automation including:
- Release notes generation from PRs
- PR review and guideline checking
- UI testing recommendations and test note generation
- Code research and analysis
- and more

The agents are designed to integrate with Slack, Azure DevOps, GitLab, and other
development tools to provide consistent AI assistance across your development workflow.
"""

__version__ = "1.0.0"
__author__ = "Dev Agents Team"
__email__ = "dev@codeligence.com"

from core.config import BaseConfig
from core.prompts import BasePrompts

__all__ = [
    "BaseConfig",
    "BasePrompts",
]
