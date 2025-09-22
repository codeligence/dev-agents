# Copyright (C) 2025 Codeligence
#
# This file is part of Dev Agents.
#
# Dev Agents is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Dev Agents is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Dev Agents.  If not, see <https://www.gnu.org/licenses/>.


from dataclasses import dataclass
from typing import cast

from pydantic import BaseModel, Field

from core.config import BaseConfig
from core.prompts import BasePrompts


@dataclass
class ChangelogEntry:
    """Simple changelog entry."""

    description: (
        str  # Includes category prefix like "Changed: Enhanced free game mechanics..."
    )
    issue_id: str | None = None


class ChangelogReport(BaseModel):
    """Simple changelog entries for a single file."""

    file_path: str
    entries: list[ChangelogEntry] = Field(default_factory=list)

    def has_entries(self) -> bool:
        """Check if this report has any changelog entries."""
        return len(self.entries) > 0


@dataclass
class ChangelogResult:
    """Combined result of changelog generation for all files."""

    reports: list[ChangelogReport]

    def get_all_entries(self) -> list[ChangelogEntry]:
        """Get all changelog entries from all reports."""
        all_entries = []
        for report in self.reports:
            all_entries.extend(report.entries)
        return all_entries

    def format_changelog(self, version: str = "") -> str:
        """Format as a simple list of changelog entries."""
        lines = []

        if version:
            lines.append(f"# {version}\n")

        all_entries = self.get_all_entries()
        for entry in all_entries:
            issue_suffix = f" ({entry.issue_id})" if entry.issue_id else ""
            lines.append(f"- {entry.description}{issue_suffix}")

        if not all_entries:
            lines.append("No significant changes detected.")

        return "\n".join(lines)


class ChangelogConfig(BaseConfig):
    """Typed configuration wrapper for changelog generation settings."""

    def __init__(self, base_config: BaseConfig):
        # Initialize parent with the same config path
        super().__init__(base_config=base_config)

    def get_max_files(self) -> int:
        """Get maximum number of files to analyze (default: 200)."""
        return int(self.get_value("subagents.changelog.maxFiles", 200))

    def get_analysis_model(self) -> str:
        """Get the LLM model for changelog analysis."""
        return cast("str", self.get_value("subagents.changelog.analysisModel"))

    def get_summary_model(self) -> str:
        """Get the LLM model for changelog summaries."""
        return cast("str", self.get_value("subagents.changelog.summaryModel"))

    def get_num_retries(self) -> int:
        """Get number of retries for failed requests (default: 3)."""
        return int(self.get_value("subagents.changelog.retries", 3))


class ChangelogPrompts(BasePrompts):
    """Typed prompts wrapper for changelog generation."""

    def __init__(self, base_prompts: BasePrompts):
        # Initialize parent with the same prompts path
        super().__init__(base_prompts._prompts_path)

    def get_changelog_generation_prompt(self) -> str:
        """Get the changelog generation system prompt."""
        return self.get_prompt("agents.changelog.changelog_generation")

    def get_file_instruction_prompt(self) -> str:
        """Get the file instruction prompt template."""
        return self.get_prompt("agents.changelog.file_instruction_prompt")

    def get_changelog_summary_prompt(self) -> str:
        """Get the changelog summary system prompt."""
        return self.get_prompt("agents.changelog.changelog_summary")
