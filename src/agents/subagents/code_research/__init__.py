"""Code Research Subagent

This subagent provides file search and content analysis capabilities
used by test plan agents to research code changes and dependencies.
"""

from .code_research_agent import create_code_research_subagent
from .models import CodeResearchConfig, CodeResearchDependencies

__all__ = [
    "CodeResearchConfig",
    "CodeResearchDependencies",
    "create_code_research_subagent",
]
