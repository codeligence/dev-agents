"""Code Research Subagent

This subagent provides file search and content analysis capabilities
used by impact analysis agents to research code changes and dependencies.
"""

from .models import CodeResearchDependencies
from .code_research_agent import create_code_research_agent

__all__ = [
    'CodeResearchDependencies',
    'create_code_research_agent'
]