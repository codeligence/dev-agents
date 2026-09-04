import asyncio
import logging

from core.integrations.provider_registry import ProviderRegistry
from core.project_config import ProjectConfig
from core.protocols import IssueModel, PullRequestModel
from core.protocols.provider_protocols import IssueProvider, PullRequestProvider
from integrations.git.config import GitRepositoryConfig
from integrations.git.git_repository import GitRepository

# Per-repository-path locks to serialize concurrent auto-clones.
_clone_locks: dict[str, asyncio.Lock] = {}


class ContextIntegrationLoader:
    """Centralized loader for pull requests and issues with caching support."""

    def __init__(self, project_config: ProjectConfig):
        self.project_config = project_config
        self._provider_registry: ProviderRegistry | None = None
        self._logger: logging.Logger | None = None

        # In-memory cache for loaded models
        self._pr_cache: dict[str, PullRequestModel] = {}
        self._issue_cache: dict[str, IssueModel] = {}

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

    async def load_pullrequest(self, pullrequest_id: str) -> PullRequestModel:
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

    async def load_issue(self, issue_id: str) -> IssueModel:
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

        # Ensure the working copy exists before resolving refs against it.
        await self.ensure_repository_available()

        # Extract branch information from the model using refs lists
        source_branch = self._resolve_refs_to_branch(pr_model.source_refs)
        target_branch = self._resolve_refs_to_branch(pr_model.target_refs)

        if not source_branch or not target_branch:
            raise ValueError(
                f"Pull request {pullrequest_id} - could not resolve valid source/target references"
            )

        return source_branch, target_branch

    async def ensure_repository_available(self) -> None:
        """Clone the configured repository if its directory is empty.

        Only an empty (or non-existent) directory is cloned into, matching
        ``git clone``'s own requirement; an existing checkout is left as-is and
        a populated non-git directory is never touched. Idempotent and safe
        under concurrency: returns immediately when the repository already
        exists, and serializes concurrent clones per repository path via
        :data:`_clone_locks`. Cloning uses the configured pull request
        provider's credentials.

        Raises:
            ValueError: If no pull request provider is available to clone with
        """
        git_config = GitRepositoryConfig.from_project_config(self.project_config)
        if git_config.has_git_repo():
            return

        repo_dir = git_config.get_repo_dir()
        if not git_config.is_repo_dir_empty():
            # Populated but not a git checkout: outside the "clone when empty"
            # contract, and git clone would reject a non-empty target.
            self._get_logger().debug(
                f"Repository directory '{repo_dir}' is not empty and not a git "
                "checkout; skipping auto-clone"
            )
            return

        lock = _clone_locks.setdefault(repo_dir, asyncio.Lock())
        async with lock:
            # Re-check after acquiring the lock: while waiting, another task may
            # have cloned the repo or the directory may have been populated.
            if git_config.has_git_repo() or not git_config.is_repo_dir_empty():
                return

            provider = self.get_pullrequest_provider()
            if provider is None:
                raise ValueError(
                    "No pull request provider available to clone repository"
                )

            self._get_logger().info(
                f"Repository directory '{repo_dir}' is empty; cloning"
            )
            await provider.clone(repo_dir)

    def _resolve_refs_to_branch(self, refs: list[str]) -> str | None:
        return GitRepository(self.project_config).resolve_refs_to_branch(refs)

    def get_project_config(self) -> ProjectConfig:
        """Get the project configuration for this loader.

        Returns:
            ProjectConfig instance used by this loader
        """
        return self.project_config

    def get_issue_provider(self) -> IssueProvider | None:
        """Get the configured issue provider for this project.

        Returns:
            Issue provider instance or None if not available
        """
        return self._get_provider_registry().resolve_issue_provider(self.project_config)

    def get_pullrequest_provider(self) -> PullRequestProvider | None:
        """Get the configured pull request provider for this project.

        Returns:
            Pull request provider instance or None if not available
        """
        return self._get_provider_registry().resolve_pullrequest_provider(
            self.project_config
        )

    def clear_cache(self) -> None:
        """Clear all cached models."""
        self._pr_cache.clear()
        self._issue_cache.clear()
        self._get_logger().debug("Cleared ProjectLoader cache")
