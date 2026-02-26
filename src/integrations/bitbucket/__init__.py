from core.integrations import get_provider_registry

from .config import BitBucketConfig
from .provider import BitBucketPullRequestProvider

# Register BitBucket provider with the global registry
registry = get_provider_registry()
registry.register_pullrequest_provider(
    "bitbucket", BitBucketPullRequestProvider.from_config
)

__all__ = ["BitBucketPullRequestProvider", "BitBucketConfig"]
