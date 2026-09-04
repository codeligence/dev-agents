from typing import Any

from core.config import BaseConfig


class GitHubConfig:
    """GitHub specific configuration class that works with BaseConfig composition.

    ``allowInsecureCloneUrl`` is **development-only**: it permits ``http://``
    clone URLs. The clone URL must still point at the web host derived from
    ``api_url``.
    """

    def __init__(self, base_config: BaseConfig):
        """Initialize with a BaseConfig instance.

        Args:
            base_config: BaseConfig instance for accessing configuration
        """
        self._base_config = base_config
        self._config_data = base_config.get_config_data()

    @classmethod
    def from_config_data(cls, config_data: dict[str, Any]) -> "GitHubConfig":
        """Create instance from configuration dictionary subset.

        Args:
            config_data: GitHub configuration dictionary

        Returns:
            GitHubConfig instance
        """
        # For compatibility with the provider factory pattern
        from core.config import BaseConfig

        base_config = BaseConfig()
        # Override the github section with provided data
        base_config._config_data["github"] = config_data
        return cls(base_config)

    def get_api_url(self) -> str | None:
        """Get the GitHub API URL."""
        value = self._base_config.get_value("github.api_url")
        return str(value) if value is not None else None

    def get_owner(self) -> str | None:
        """Get the GitHub repository owner."""
        value = self._base_config.get_value("github.owner")
        return str(value) if value is not None else None

    def get_repo(self) -> str | None:
        """Get the GitHub repository name."""
        value = self._base_config.get_value("github.repo")
        return str(value) if value is not None else None

    def get_token(self) -> str | None:
        """Get the GitHub personal access token."""
        value = self._base_config.get_value("github.token")
        return str(value) if value is not None else None

    def get_use_mocks(self) -> bool:
        """Get the GitHub mock mode setting."""
        return self._base_config.get_bool("github.mock")

    def get_allow_insecure_clone_url(self) -> bool:
        """Whether ``http://`` clone URLs are permitted (development only)."""
        return self._base_config.get_bool("github.allowInsecureCloneUrl")

    def is_configured(self) -> bool:
        """Check if all required GitHub configuration is present."""

        if self.get_use_mocks():
            return True

        required_fields = [
            self.get_api_url(),
            self.get_owner(),
            self.get_repo(),
            self.get_token(),
        ]
        return all(field is not None and field != "" for field in required_fields)
