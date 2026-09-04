from typing import Any

from core.config import parse_bool


class AzureDevOpsConfig:
    """Azure DevOps specific configuration class that works with project config subsets.

    ``allowInsecureCloneUrl`` is **development-only**: it permits an
    ``http://`` ``url`` to be used for cloning. The clone URL must still point
    at the host of ``url``.
    """

    def __init__(self, config_data: dict[str, Any]):
        """Initialize with a configuration dictionary subset.

        Args:
            config_data: Azure DevOps configuration dictionary
        """
        self._config_data = config_data or {}

    def get_url(self) -> str | None:
        """Get the Azure DevOps URL."""
        return self._config_data.get("url")

    def get_organization(self) -> str | None:
        """Get the Azure DevOps organization."""
        return self._config_data.get("organization")

    def get_project(self) -> str | None:
        """Get the Azure DevOps project."""
        return self._config_data.get("project")

    def get_pat(self) -> str | None:
        """Get the Azure DevOps Personal Access Token."""
        return self._config_data.get("pat")

    def get_repo_id(self) -> str | None:
        """Get the Azure DevOps repository ID."""
        return self._config_data.get("repoId")

    def get_use_mocks(self) -> bool:
        """Get the Azure DevOps mock mode setting."""
        return parse_bool(self._config_data.get("mock", "false"))

    def get_allow_insecure_clone_url(self) -> bool:
        """Whether ``http://`` clone URLs are permitted (development only)."""
        return parse_bool(self._config_data.get("allowInsecureCloneUrl", "false"))

    def is_configured(self) -> bool:
        """Check if all required Azure DevOps configuration is present."""

        if self.get_use_mocks():
            return True

        required_fields = [
            self.get_url(),
            self.get_organization(),
            self.get_project(),
            self.get_pat(),
            self.get_repo_id(),
        ]
        return all(field is not None and field != "" for field in required_fields)
