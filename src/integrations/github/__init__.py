from core.integrations import get_provider_registry

from .config import GitHubConfig
from .provider import GitHubIssueProvider, GitHubPullRequestProvider

# Register GitHub providers with the global registry
registry = get_provider_registry()
registry.register_pullrequest_provider("github", GitHubPullRequestProvider.from_config)
registry.register_issue_provider("github", GitHubIssueProvider.from_config)

__all__ = ["GitHubPullRequestProvider", "GitHubIssueProvider", "GitHubConfig"]
