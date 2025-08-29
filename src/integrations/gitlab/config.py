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


from typing import Any


class GitLabConfig:
    """GitLab specific configuration class that works with project config subsets."""

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
        mock_value = self._config_data.get("mock", "false")
        # Handle both boolean and string representations
        if isinstance(mock_value, bool):
            return mock_value
        return str(mock_value).lower() in ("true", "1", "yes", "on")

    def is_configured(self) -> bool:
        """Check if all required GitLab configuration is present."""

        if self.get_use_mocks():
            return True

        required_fields = [self.get_api_url(), self.get_project_id(), self.get_token()]
        return all(field is not None and field != "" for field in required_fields)
