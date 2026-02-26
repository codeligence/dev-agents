"""Claude Code Subagent

This subagent performs codebase research and analysis using Claude SDK,
configured with read-only tools for safe exploration.
"""

from .claude_code_subagent import ClaudeCodeSubagent
from .models import ClaudeCodeConfig

__all__ = [
    "ClaudeCodeConfig",
    "ClaudeCodeSubagent",
]
