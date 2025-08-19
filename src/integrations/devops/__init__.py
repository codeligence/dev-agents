from .provider import AzureDevOpsPullRequestProvider, AzureDevOpsIssueProvider
from .config import AzureDevOpsConfig
from core.integrations import get_provider_registry

# Register Azure DevOps providers with the global registry
registry = get_provider_registry()
registry.register_pullrequest_provider("devops", AzureDevOpsPullRequestProvider.from_config)
registry.register_issue_provider("devops", AzureDevOpsIssueProvider.from_config)

__all__ = ["AzureDevOpsPullRequestProvider", "AzureDevOpsIssueProvider", "AzureDevOpsConfig"]