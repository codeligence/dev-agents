from abc import abstractmethod
from typing import Protocol, Optional, Dict, Any, List
from dataclasses import dataclass, field


@dataclass
class PullRequestModel:
    """Model representing a pull request from any provider."""
    id: str
    context: str
    source_branch: Optional[str] = None
    target_branch: Optional[str] = None
    source_refs: List[str] = field(default_factory=list)
    target_refs: List[str] = field(default_factory=list)


@dataclass
class IssueModel:
    """Model representing an issue/work item from any provider."""
    id: str
    context: str


class PullRequestProvider(Protocol):
    """Protocol for pull request providers (Azure DevOps, GitHub, GitLab, etc.)."""

    @staticmethod
    @abstractmethod
    def from_config(config: Dict[str, Any]) -> Optional['PullRequestProvider']:
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
    def from_config(config: Dict[str, Any]) -> Optional['IssueProvider']:
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
