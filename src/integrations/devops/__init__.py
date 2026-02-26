from core.integrations import get_provider_registry

from .config import AzureDevOpsConfig
from .provider import AzureDevOpsIssueProvider, AzureDevOpsPullRequestProvider

# Register Azure DevOps providers with the global registry
registry = get_provider_registry()
registry.register_pullrequest_provider(
    "devops", AzureDevOpsPullRequestProvider.from_config
)
registry.register_issue_provider("devops", AzureDevOpsIssueProvider.from_config)

__all__ = [
    "AzureDevOpsPullRequestProvider",
    "AzureDevOpsIssueProvider",
    "AzureDevOpsConfig",
]
