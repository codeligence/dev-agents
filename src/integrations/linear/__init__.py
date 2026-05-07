from core.integrations import get_provider_registry

from .config import LinearConfig
from .provider import LinearIssueProvider

# Register Linear providers with the global registry
registry = get_provider_registry()
registry.register_issue_provider("linear", LinearIssueProvider.from_config)

__all__ = ["LinearIssueProvider", "LinearConfig"]
