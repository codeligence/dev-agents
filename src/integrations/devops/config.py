from typing import Optional, Dict, Any


class AzureDevOpsConfig:
    """Azure DevOps specific configuration class that works with project config subsets."""

    def __init__(self, config_data: Dict[str, Any]):
        """Initialize with a configuration dictionary subset.
        
        Args:
            config_data: Azure DevOps configuration dictionary
        """
        self._config_data = config_data or {}


    def get_url(self) -> Optional[str]:
        """Get the Azure DevOps URL."""
        return self._config_data.get('url')

    def get_organization(self) -> Optional[str]:
        """Get the Azure DevOps organization."""
        return self._config_data.get('organization')

    def get_project(self) -> Optional[str]:
        """Get the Azure DevOps project."""
        return self._config_data.get('project')

    def get_pat(self) -> Optional[str]:
        """Get the Azure DevOps Personal Access Token."""
        return self._config_data.get('pat')

    def get_repo_id(self) -> Optional[str]:
        """Get the Azure DevOps repository ID."""
        return self._config_data.get('repoId')

    def get_use_mocks(self) -> bool:
        """Get the Azure DevOps mock mode setting."""
        mock_value = self._config_data.get('mock', 'false')
        # Handle both boolean and string representations
        if isinstance(mock_value, bool):
            return mock_value
        return str(mock_value).lower() in ('true', '1', 'yes', 'on')

    def is_configured(self) -> bool:
        """Check if all required Azure DevOps configuration is present."""
        required_fields = [
            self.get_url(),
            self.get_organization(),
            self.get_project(),
            self.get_pat(),
            self.get_repo_id()
        ]
        return all(field is not None and field != "" for field in required_fields)
