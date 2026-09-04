from typing import Any

from core.config import parse_bool


class GitLabConfig:
    """GitLab specific configuration class that works with project config subsets.

    ``allowInsecureCloneUrl`` is **development-only**: it permits ``http://``
    clone URLs returned by the GitLab API. The clone URL must still point at
    the host of ``api_url``.
    """

    def __init__(self, config_data: dict[str, Any]):
        """Initialize with a configuration dictionary subset.

        Args:
            config_data: GitLab configuration dictionary
        """
        self._config_data = config_data or {}

    def get_api_url(self) -> str | None:
        """Get the GitLab API URL."""
        return self._config_data.get("api_url")

    def get_project_id(self) -> str | None:
        """Get the GitLab project ID."""
        return self._config_data.get("project_id")

    def get_token(self) -> str | None:
        """Get the GitLab personal access token."""
        return self._config_data.get("token")

    def get_use_mocks(self) -> bool:
        """Get the GitLab mock mode setting."""
        return parse_bool(self._config_data.get("mock", "false"))

    def get_allow_insecure_clone_url(self) -> bool:
        """Whether ``http://`` clone URLs are permitted (development only)."""
        return parse_bool(self._config_data.get("allowInsecureCloneUrl", "false"))

    def is_configured(self) -> bool:
        """Check if all required GitLab configuration is present."""

        if self.get_use_mocks():
            return True

        required_fields = [self.get_api_url(), self.get_project_id(), self.get_token()]
        return all(field is not None and field != "" for field in required_fields)
