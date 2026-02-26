from core.integrations import get_provider_registry

from .config import GitLabConfig
from .provider import (
    GitLabIssueProvider,
    GitLabMergeRequestProvider,
    GitLabPipelineProvider,
)

# Register GitLab providers with the global registry
registry = get_provider_registry()
registry.register_pullrequest_provider("gitlab", GitLabMergeRequestProvider.from_config)
registry.register_issue_provider("gitlab", GitLabIssueProvider.from_config)
registry.register_pipeline_provider("gitlab", GitLabPipelineProvider.from_config)

__all__ = [
    "GitLabMergeRequestProvider",
    "GitLabIssueProvider",
    "GitLabPipelineProvider",
    "GitLabConfig",
]
