# Copyright (C) 2025 Codeligence
#
# This file is part of Dev Agents.
#
# Dev Agents is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Dev Agents is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Dev Agents.  If not, see <https://www.gnu.org/licenses/>.


from typing import Optional, Dict, Any, List, TYPE_CHECKING

from core.exceptions import ConfigurationError

if TYPE_CHECKING:
    from core.config import BaseConfig


class ProjectConfig:
    """Configuration wrapper for a specific project."""

    def __init__(self, project_name: str, base_config: 'BaseConfig'):
        self.project_name = project_name
        self._base_config = base_config
        self._project_key = f"projects.{project_name}"

    def get_git_config(self) -> Dict[str, Any]:
        """Get git configuration for this project."""
        git_config = self._base_config.get_value(f"{self._project_key}.git", {})
        if not git_config:
            raise ConfigurationError(f"No git configuration found for project '{self.project_name}'")
        return git_config

    def get_pullrequest_providers(self) -> Dict[str, Dict[str, Any]]:
        """Get all configured pull request providers for this project."""
        return self._base_config.get_value(f"{self._project_key}.pullrequests", {})

    def get_issue_providers(self) -> Dict[str, Dict[str, Any]]:
        """Get all configured issue providers for this project."""
        return self._base_config.get_value(f"{self._project_key}.issues", {})

    def get_provider_config(self, provider_type: str, provider_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific provider.

        Args:
            provider_type: 'pullrequests' or 'issues'
            provider_name: Provider name (e.g., 'devops', 'github', 'jira')

        Returns:
            Provider configuration dict or None if not found
        """
        providers = self._base_config.get_value(f"{self._project_key}.{provider_type}", {})
        return providers.get(provider_name)

    def is_configured(self) -> bool:
        """Check if this project has basic configuration."""
        try:
            git_config = self.get_git_config()
            return bool(git_config.get("path"))
        except ConfigurationError:
            return False


class ProjectConfigFactory:
    """Factory for creating project configurations."""

    def __init__(self, base_config: 'BaseConfig'):
        self._base_config = base_config

    def get_available_projects(self) -> List[str]:
        """Get list of configured project names."""
        projects = self._base_config.get_value("projects", {})
        return list(projects.keys())

    def get_project_config(self, project_name: str) -> ProjectConfig:
        """Get configuration for a specific project.

        Args:
            project_name: Name of the project

        Returns:
            ProjectConfig instance

        Raises:
            ConfigurationError: If project is not found
        """
        projects = self._base_config.get_value("projects", {})
        if project_name not in projects:
            available = ", ".join(self.get_available_projects())
            raise ConfigurationError(
                f"Project '{project_name}' not found in configuration. "
                f"Available projects: {available}"
            )

        return ProjectConfig(project_name, self._base_config)

    def get_default_project_config(self) -> ProjectConfig:
        """Get the default project configuration."""
        return self.get_project_config("default")

