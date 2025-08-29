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


from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol


@dataclass
class PullRequestModel:
    """Model representing a pull request from any provider."""

    id: str
    context: str
    source_branch: str | None = None
    target_branch: str | None = None
    source_refs: list[str] = field(default_factory=list)
    target_refs: list[str] = field(default_factory=list)


@dataclass
class IssueModel:
    """Model representing an issue/work item from any provider."""

    id: str
    context: str


class PullRequestProvider(Protocol):
    """Protocol for pull request providers (Azure DevOps, GitHub, GitLab, etc.)."""

    @staticmethod
    @abstractmethod
    def from_config(config: dict[str, Any]) -> Optional["PullRequestProvider"]:
        """Create provider instance from configuration.

        Args:
            config: Provider-specific configuration dictionary

        Returns:
            Provider instance if config is valid, None otherwise
        """
        ...

    @abstractmethod
    async def load(self, pull_request_id: str) -> PullRequestModel:
        """Load pull request by ID.

        Args:
            pull_request_id: Pull request identifier

        Returns:
            PullRequestModel with id and context

        Raises:
            ProviderError: If pull request cannot be loaded
        """
        ...


class IssueProvider(Protocol):
    """Protocol for issue providers (Azure DevOps, Jira, GitHub Issues, etc.)."""

    @staticmethod
    @abstractmethod
    def from_config(config: dict[str, Any]) -> Optional["IssueProvider"]:
        """Create provider instance from configuration.

        Args:
            config: Provider-specific configuration dictionary

        Returns:
            Provider instance if config is valid, None otherwise
        """
        ...

    @abstractmethod
    async def load(self, issue_id: str) -> IssueModel:
        """Load issue/work item by ID.

        Args:
            issue_id: Issue identifier

        Returns:
            IssueModel with id and context

        Raises:
            ProviderError: If issue cannot be loaded
        """
        ...
