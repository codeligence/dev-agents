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


from typing import Any
import logging

from core.integrations.provider_registry import ProviderRegistry
from core.project_config import ProjectConfig
from integrations.git.git_repository import GitRepository


class ContextIntegrationLoader:
    """Centralized loader for pull requests and issues with caching support."""

    def __init__(self, project_config: ProjectConfig):
        self.project_config = project_config
        self._provider_registry: ProviderRegistry | None = None
        self._logger: logging.Logger | None = None

        # In-memory cache for loaded models
        self._pr_cache: dict[str, Any] = {}
        self._issue_cache: dict[str, Any] = {}

    def _get_provider_registry(self) -> ProviderRegistry:
        """Lazy initialization of provider registry to avoid circular imports."""
        if self._provider_registry is None:
            from core.integrations import get_provider_registry

            self._provider_registry = get_provider_registry()
        return self._provider_registry

    def _get_logger(self) -> logging.Logger:
        """Lazy initialization of logger."""
        if self._logger is None:
            from core.log import get_logger

            self._logger = get_logger("ProjectLoader")
        return self._logger

    async def load_pullrequest(self, pullrequest_id: str) -> Any:
        """Load pull request model with caching.

        Args:
            pullrequest_id: Pull Request ID

        Returns:
            Pull request model from provider

        Raises:
            ValueError: If no pull request provider available or PR not found
        """
        # Check cache first
        if pullrequest_id in self._pr_cache:
            self._get_logger().debug(f"Returning cached PR #{pullrequest_id}")
            return self._pr_cache[pullrequest_id]

        # Load from provider
        pr_provider = self._get_provider_registry().resolve_pullrequest_provider(
            self.project_config
        )
        if not pr_provider:
            raise ValueError(
                "No pull request provider available for current configuration"
            )

        self._get_logger().info(f"Loading PR #{pullrequest_id} from provider")
        pr_model = await pr_provider.load(pullrequest_id)

        # Cache the result
        self._pr_cache[pullrequest_id] = pr_model
        return pr_model

    async def load_issue(self, issue_id: str) -> Any:
        """Load issue model with caching.

        Args:
            issue_id: Issue ID

        Returns:
            Issue model from provider

        Raises:
            ValueError: If no issue provider available or issue not found
        """
        # Check cache first
        if issue_id in self._issue_cache:
            self._get_logger().debug(f"Returning cached issue #{issue_id}")
            return self._issue_cache[issue_id]

        # Load from provider
        issue_provider = self._get_provider_registry().resolve_issue_provider(
            self.project_config
        )
        if not issue_provider:
            raise ValueError("No issue provider available for current configuration")

        self._get_logger().info(f"Loading issue #{issue_id} from provider")
        issue_model = await issue_provider.load(issue_id)

        # Cache the result
        self._issue_cache[issue_id] = issue_model
        return issue_model

    async def get_branches_from_pr(self, pullrequest_id: str) -> tuple[str, str]:
        """Get source and target branch names from a pull request.

        Args:
            pullrequest_id: Pull Request ID

        Returns:
            Tuple of (source_branch, target_branch)

        Raises:
            ValueError: If branches cannot be resolved from PR
        """
        pr_model = await self.load_pullrequest(pullrequest_id)

        # Extract branch information from the model using refs lists
        source_branch = self._resolve_refs_to_branch(pr_model.source_refs)
        target_branch = self._resolve_refs_to_branch(pr_model.target_refs)

        if not source_branch or not target_branch:
            raise ValueError(
                f"Pull request {pullrequest_id} - could not resolve valid source/target references"
            )

        return source_branch, target_branch

    def _resolve_refs_to_branch(self, refs: list[str]) -> str | None:
        return GitRepository(self.project_config).resolve_refs_to_branch(refs)

    def clear_cache(self) -> None:
        """Clear all cached models."""
        self._pr_cache.clear()
        self._issue_cache.clear()
        self._get_logger().debug("Cleared ProjectLoader cache")
