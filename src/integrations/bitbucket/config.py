from typing import Any


class BitBucketConfig:
    """BitBucket specific configuration class that works with project config subsets."""

    DEFAULT_API_URL = "https://api.bitbucket.org/2.0"

    def __init__(self, config_data: dict[str, Any]):
        """Initialize with a configuration dictionary subset.

        Args:
            config_data: BitBucket configuration dictionary
        """
        self._config_data = config_data or {}

    def get_api_url(self) -> str:
        """Get the BitBucket API URL.

        Returns:
            API URL, defaults to https://api.bitbucket.org/2.0
        """
        url = self._config_data.get("api_url")
        if url and str(url).strip():
            return str(url)
        return self.DEFAULT_API_URL

    def get_workspace(self) -> str | None:
        """Get the BitBucket workspace (team/user)."""
        return self._config_data.get("workspace")

    def get_repo_slug(self) -> str | None:
        """Get the BitBucket repository slug."""
        return self._config_data.get("repo_slug")

    def get_username(self) -> str | None:
        """Get the BitBucket username (Atlassian account email)."""
        return self._config_data.get("username")

    def get_token(self) -> str | None:
        """Get the BitBucket API token (App password)."""
        return self._config_data.get("token")

    def get_use_mocks(self) -> bool:
        """Get the BitBucket mock mode setting."""
        mock_value = self._config_data.get("mock", "false")
        # Handle both boolean and string representations
        if isinstance(mock_value, bool):
            return mock_value
        return str(mock_value).lower() in ("true", "1", "yes", "on")

    def is_configured(self) -> bool:
        """Check if all required BitBucket configuration is present."""
        if self.get_use_mocks():
            return True

        required_fields = [
            self.get_workspace(),
            self.get_repo_slug(),
            self.get_username(),
            self.get_token(),
        ]
        return all(field is not None and field != "" for field in required_fields)
