from core.integrations import get_provider_registry

from .config import JiraConfig
from .provider import JiraIssueProvider

# Register Jira providers with the global registry
registry = get_provider_registry()
registry.register_issue_provider("jira", JiraIssueProvider.from_config)

__all__ = ["JiraIssueProvider", "JiraConfig"]
