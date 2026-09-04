from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, Protocol

from core.git.clone import clone_repository
from core.git.clone_url import validate_clone_url


@dataclass
class CloneSpec:
    """Where and how to clone a provider's repository.

    The URL must be credential-free; ``clone_repository`` stores *user* and
    *password* in git's credential store instead of embedding them. Before
    cloning, the URL is checked against *expected_host* (hostname, optionally
    with port) and must use ``https`` unless *allow_insecure* is set, so the
    credential never travels in plaintext or to an unintended host.
    """

    url: str
    user: str
    password: str
    expected_host: str
    allow_insecure: bool = False


@dataclass
class PipelineModel:
    """Model representing a CI/CD pipeline from any provider."""

    id: str
    context: str  # Composed pipeline info for AI context
    status: str  # success, failed, running, pending, canceled, skipped
    ref: str  # Git branch or tag
    web_url: str  # Link to pipeline UI
    jobs: list[dict[str, Any]] = field(default_factory=list)
    failed_jobs: list[dict[str, Any]] = field(default_factory=list)
    duration: int | None = None
    coverage: str | None = None


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

    async def clone(self, target_dir: str) -> None:
        """Clone this provider's repository into *target_dir*.

        Template method: obtains the provider's :class:`CloneSpec` via
        :meth:`_clone_spec`, validates the clone URL against the spec's
        expected host and scheme, and delegates to ``clone_repository``, which
        keeps the credential out of process arguments and the cloned
        repository by storing it in git's credential store.

        Args:
            target_dir: Filesystem path to clone the repository into

        Raises:
            NotImplementedError: If the provider does not support cloning
            GitOperationError: If the provider is not configured for cloning,
                the clone URL fails validation or the repository cannot be
                cloned
        """
        spec = await self._clone_spec()
        if spec is None:
            return
        validate_clone_url(
            spec.url,
            expected_host=spec.expected_host,
            allow_insecure=spec.allow_insecure,
        )
        await clone_repository(
            spec.url, target_dir, user=spec.user, password=spec.password
        )

    async def _clone_spec(self) -> CloneSpec | None:
        """Return the clone URL and credentials for this provider.

        Providers that support cloning override this hook. They must return
        ``None`` when cloning should be skipped (mock mode) and raise
        ``GitOperationError`` when required configuration is missing.

        Raises:
            NotImplementedError: If the provider does not support cloning
        """
        raise NotImplementedError(f"{type(self).__name__} does not support cloning")


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

    def extract_issue_ids(self, text: str) -> list[str]:  # noqa: ARG002
        """Extract issue IDs from text.

        Args:
            text: Text to search for issue identifiers

        Returns:
            List of issue IDs found in text
        """
        return []

    async def update(
        self, issue_id: str, description: str  # noqa: ARG002
    ) -> tuple[bool, str]:
        """Update issue description.

        Default implementation returns failure. Override in providers
        that support issue updates (e.g., Jira).

        Args:
            issue_id: Issue identifier
            description: New description in Markdown format

        Returns:
            Tuple of (success: bool, message: str)
        """
        return False, "Update not supported by this provider"


@dataclass
class PipelineListFilter:
    """Filter criteria for listing pipelines."""

    ref: str | None = None
    status: str | None = None
    count: int = 20


@dataclass
class PipelineSummaryModel:
    """Lightweight model representing a pipeline in list results."""

    id: str
    status: str
    ref: str
    sha: str
    web_url: str
    created_at: str
    updated_at: str
    source: str = ""


class PipelineProvider(Protocol):
    """Protocol for CI/CD pipeline providers (GitLab CI, GitHub Actions, etc.)."""

    @staticmethod
    @abstractmethod
    def from_config(config: dict[str, Any]) -> Optional["PipelineProvider"]:
        """Create provider instance from configuration.

        Args:
            config: Provider-specific configuration dictionary

        Returns:
            Provider instance if config is valid, None otherwise
        """
        ...

    @abstractmethod
    async def load(self, pipeline_id: str) -> PipelineModel:
        """Load pipeline by ID.

        Args:
            pipeline_id: Pipeline identifier

        Returns:
            PipelineModel with pipeline data and context

        Raises:
            ProviderError: If pipeline cannot be loaded
        """
        ...

    @abstractmethod
    async def list(
        self, filters: PipelineListFilter | None = None
    ) -> list[PipelineSummaryModel]:
        """List pipelines with optional filtering.

        Args:
            filters: Optional filter criteria for ref, status, and result count

        Returns:
            List of PipelineSummaryModel with pipeline summaries

        Raises:
            ProviderError: If pipelines cannot be listed
        """
        ...

    @abstractmethod
    async def get_job_log(self, pipeline_id: str, job_id: str) -> str:
        """Get log output for a specific job.

        Args:
            pipeline_id: Pipeline identifier
            job_id: Job identifier

        Returns:
            Job log as string

        Raises:
            ProviderError: If job log cannot be retrieved
        """
        ...
