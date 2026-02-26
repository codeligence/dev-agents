from dataclasses import dataclass
from typing import cast

from core.config import BaseConfig


@dataclass
class CodeResearchDependencies:
    """Dependencies for code research agent operations."""

    git_ref: str
    repo_path: str
    max_lines: int = 2000  # Default max lines for file reads


class CodeResearchConfig:
    """Type-safe configuration class for code research subagent."""

    def __init__(self, base_config: BaseConfig):
        self._base_config = base_config

    def get_model(self) -> str:
        """Get the LLM model for code research (default from config)."""
        return cast("str", self._base_config.get_value("subagents.coderesearch.model"))

    def get_num_retries(self) -> int:
        """Get number of retries for failed requests (default: 3)."""
        return int(self._base_config.get_value("subagents.coderesearch.retries") or 3)
