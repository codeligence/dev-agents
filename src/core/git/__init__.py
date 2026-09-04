"""Git primitives that core depends on, independent of any provider integration."""

from .clone import clone_repository, web_host_from_api_url
from .clone_url import host_from_url, validate_clone_url

__all__ = [
    "clone_repository",
    "host_from_url",
    "validate_clone_url",
    "web_host_from_api_url",
]
