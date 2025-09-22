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


from typing import Any, Optional

import httpx

from core.protocols.provider_protocols import IssueModel, IssueProvider

from .config import JiraConfig
from .mock_jira import mock_fetch_issue
from .models import JiraIssue


class JiraIssueProvider(IssueProvider):
    """Jira implementation of IssueProvider."""

    def __init__(self, config: JiraConfig):
        self.config = config

    @staticmethod
    def from_config(config_data: dict[str, Any]) -> Optional["JiraIssueProvider"]:
        """Create provider from configuration data.

        Args:
            config_data: Jira configuration dictionary

        Returns:
            Provider instance if config is valid, None otherwise
        """
        config = JiraConfig(config_data)
        if not config.is_configured():
            return None
        return JiraIssueProvider(config)

    async def load(self, issue_id: str) -> IssueModel:
        """Load issue by ID.

        Args:
            issue_id: Issue identifier (key like 'PROJ-123')

        Returns:
            IssueModel with id and context
        """
        if self.config.get_use_mocks():
            issue = mock_fetch_issue(issue_id)
            context = issue.get_composed_issue_info()
        else:
            issue = await self._fetch_issue(issue_id)
            context = issue.get_composed_issue_info()

        return IssueModel(id=issue_id, context=context)

    async def _fetch_issue(self, issue_id: str) -> JiraIssue:
        """Fetch issue from Jira API.

        Args:
            issue_id: Issue identifier (key like 'PROJ-123')

        Returns:
            JiraIssue instance with API data
        """
        domain = self.config.get_domain()
        email = self.config.get_email()
        token = self.config.get_token()

        url = f"https://{domain}.atlassian.net/rest/api/3/issue/{issue_id}"

        # Include all relevant fields and expand changelog
        params = {
            "fields": "summary,description,status,assignee,creator,reporter,priority,issuetype,created,updated,resolutiondate,attachment,comment,subtasks,issuelinks,customfield_10010",
            "expand": "changelog",
        }

        headers = {"Accept": "application/json"}

        # Use HTTP Basic Auth with email and token (httpx format)
        auth = (str(email), str(token))

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, auth=auth, params=params)
            response.raise_for_status()
            return JiraIssue(response.json())
