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
from typing import Any, cast

from pydantic import BaseModel, Field

from core.config import BaseConfig
from core.prompts import BasePrompts


@dataclass
class UIComponent:
    """Represents a UI component that might be impacted by code changes."""

    name: str
    file_path: str
    component_type: str  # 'component', 'page', 'service', etc.
    dependencies: list[str]
    impact_reason: str


class UIImpactReport(BaseModel):
    """Report detailing the potential UI impacts of code changes."""

    summary: str = Field(description="Executive summary of UI impacts")
    impacted_components: list[dict[str, Any]] = Field(
        description="List of UI components that may be impacted", default_factory=list
    )
    testing_recommendations: list[str] = Field(
        description="Specific testing recommendations for UI components",
        default_factory=list,
    )
    risk_assessment: str = Field(description="Overall risk assessment for UI changes")

    def format_report(self) -> str:
        """Format the UI impact report as a markdown string."""
        lines = []
        lines.append(f"**Summary**: {self.summary}")

        if self.impacted_components:
            lines.append(f"**Components Affected**: {len(self.impacted_components)}")
            for component in self.impacted_components:
                name = component.get("name", "Unknown")
                impact_reason = component.get("impact_reason", "No reason specified")
                lines.append(f"  - {name}: {impact_reason}")

        if self.testing_recommendations:
            lines.append("**Testing Recommendations**:")
            for rec in self.testing_recommendations:
                lines.append(f"  - {rec}")

        return "\n".join(lines)


@dataclass
class ApiChange:
    """Represents an API change that might impact system functionality."""

    endpoint_or_method: str
    change_type: str  # 'modified', 'added', 'removed', 'deprecated'
    file_path: str
    impact_description: str
    breaking_change: bool = False


class ApiImpactReport(BaseModel):
    """Report detailing the potential API impacts of code changes."""

    summary: str = Field(description="Executive summary of API impacts")
    api_changes: list[dict[str, Any]] = Field(
        description="List of API changes detected", default_factory=list
    )
    breaking_changes: list[dict[str, Any]] = Field(
        description="List of breaking changes that require immediate attention",
        default_factory=list,
    )
    integration_risks: list[str] = Field(
        description="Potential integration risks and considerations",
        default_factory=list,
    )
    testing_recommendations: list[str] = Field(
        description="Specific testing recommendations for API changes",
        default_factory=list,
    )
    risk_assessment: str = Field(description="Overall risk assessment for API changes")

    def format_report(self) -> str:
        """Format the API impact report as a markdown string."""
        lines = []
        lines.append(f"**Summary**: {self.summary}")

        if self.api_changes:
            lines.append(f"**API Changes**: {len(self.api_changes)}")
            for change in self.api_changes:
                endpoint = change.get("endpoint_or_method", "Unknown")
                change_type = change.get("change_type", "Unknown")
                description = change.get("impact_description", "No description")
                lines.append(f"  - {endpoint} ({change_type}): {description}")

        if self.breaking_changes:
            lines.append(f"**Breaking Changes**: {len(self.breaking_changes)}")
            for change in self.breaking_changes:
                endpoint = change.get("endpoint_or_method", "Unknown")
                description = change.get("impact_description", "No description")
                lines.append(f"  - ⚠️ {endpoint}: {description}")

        if self.integration_risks:
            lines.append("**Integration Risks**:")
            for risk in self.integration_risks:
                lines.append(f"  - {risk}")

        if self.testing_recommendations:
            lines.append("**Testing Recommendations**:")
            for rec in self.testing_recommendations:
                lines.append(f"  - {rec}")

        return "\n".join(lines)


@dataclass
class ImpactAnalysisResult:
    """Combined result of UI and API impact analysis."""

    ui_impacts: list[UIImpactReport]
    api_impacts: list[ApiImpactReport]

    @property
    def has_any_impact(self) -> bool:
        """Whether any impact was detected."""
        return len(self.ui_impacts) > 0 or len(self.api_impacts) > 0

    def summary(self) -> str:
        """Generate a comprehensive markdown summary of the impact analysis."""
        summary_lines = ["# Comprehensive Change Impact Analysis"]

        if self.ui_impacts:
            total_ui_components = sum(
                len(ui_report.impacted_components) for ui_report in self.ui_impacts
            )
            summary_lines.append("\n## Frontend Impact Summary")
            summary_lines.append(
                f"- **Files analyzed**: {len(self.ui_impacts)} frontend files"
            )
            summary_lines.append(f"- **UI components affected**: {total_ui_components}")

            summary_lines.append("\n### UI Impact Details")
            for i, ui_report in enumerate(self.ui_impacts, 1):
                summary_lines.append(f"\n#### Frontend Analysis {i}")
                summary_lines.append(ui_report.format_report())

        if self.api_impacts:
            total_api_components = sum(
                len(api_report.api_changes) for api_report in self.api_impacts
            )
            summary_lines.append("\n## Backend Impact Summary")
            summary_lines.append(
                f"- **Files analyzed**: {len(self.api_impacts)} backend files"
            )
            summary_lines.append(
                f"- **API components affected**: {total_api_components}"
            )

            summary_lines.append("\n### API Impact Details")
            for i, api_report in enumerate(self.api_impacts, 1):
                summary_lines.append(f"\n#### Backend Analysis {i}")
                summary_lines.append(api_report.format_report())

        if not self.ui_impacts and not self.api_impacts:
            summary_lines.append("\n## No Impact Detected")
            summary_lines.append(
                "No specific frontend or backend impacts were identified in the analyzed files."
            )

        summary_report = (
            "\n".join(summary_lines)
            + "\n\n\nUse this output to craft the user response in fenced markdown (encapsulated in ```)"
        )

        return summary_report


class ImpactAnalysisConfig(BaseConfig):
    """Typed configuration wrapper for impact analysis settings."""

    def __init__(self, base_config: BaseConfig):
        # Initialize parent with the same config path
        super().__init__(base_config=base_config)

    def get_max_files(self) -> int:
        """Get maximum number of files to analyze (default: 200)."""
        return int(self.get_value("subagents.impactanalysis.maxFiles", 200))

    def get_impact_analysis_model(self) -> str:
        """Get the LLM model for code research (default: 'openai:gpt-4o-mini')."""
        return cast("str", self.get_value("subagents.impactanalysis.model"))

    def get_code_research_model(self) -> str:
        """Get the LLM model for code research (default: 'openai:gpt-4o-mini')."""
        return cast("str", self.get_value("subagents.coderesearch.model"))

    def get_num_retries(self) -> int:
        """Get number of retries for failed requests (default: 3)."""
        return int(self.get_value("subagents.impactanalysis.retries", 3))

    def get_frontend_patterns(self) -> list[str]:
        """Get frontend file classification patterns."""
        patterns = self.get_value(
            "subagents.impactanalysis.fileClassification.frontendPatterns", []
        )
        if not patterns:
            # Fallback to default patterns if config not available
            return [
                r".*\.(js|ts|jsx|tsx)$",
                r".*\.(html|htm)$",
                r".*\.(css|scss|sass|less)$",
                r".*\.(vue|svelte)$",
                r".*/src/app/.*",
                r".*/components?/.*\.(js|ts|jsx|tsx)$",
            ]
        return cast("list[str]", patterns)

    def get_backend_patterns(self) -> list[str]:
        """Get backend file classification patterns."""
        patterns = self.get_value(
            "subagents.impactanalysis.fileClassification.backendPatterns", []
        )
        if not patterns:
            # Fallback to default patterns if config not available
            return [
                r".*\.(cs|java|py|php|rb|go|rs)$",
                r".*\.cs$",
                r".*Controller\.cs$",
                r".*/Models?/.*\.cs$",
                r".*/Services?/.*\.cs$",
                r".*appsettings.*\.json$",
                r".*\.sql$",
            ]
        return cast("list[str]", patterns)


class ImpactAnalysisPrompts(BasePrompts):
    """Typed prompts wrapper for impact analysis."""

    def __init__(self, base_prompts: BasePrompts):
        # Initialize parent with the same prompts path
        super().__init__(base_prompts._prompts_path)

    def get_ui_impact_prompt(self) -> str:
        """Get the UI impact analysis system prompt."""
        return self.get_prompt("agents.impactanalysis.ui_impact_analysis")

    def get_api_impact_prompt(self) -> str:
        """Get the API impact analysis system prompt."""
        return self.get_prompt("agents.impactanalysis.api_impact_analysis")

    def get_file_instruction_prompt(self) -> str:
        """Get the file instruction prompt template."""
        return self.get_prompt("agents.impactanalysis.file_instruction_prompt")
