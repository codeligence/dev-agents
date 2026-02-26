from typing import Any, Optional
import re

import httpx

from core.protocols.provider_protocols import IssueModel, IssueProvider
from core.storage import get_storage

from .client_service import JiraClientService
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

            # Describe images if model is configured
            image_descriptions = None
            image_model = self.config.get_image_model()
            if image_model:
                client = JiraClientService(self.config)
                storage = get_storage()
                image_descriptions = await client.describe_image_attachments_cached(
                    issue, image_model, storage
                )

            context = issue.get_composed_issue_info(image_descriptions)

        return IssueModel(id=issue_id, context=context)

    def extract_issue_ids(self, text: str) -> list[str]:
        """Extract Jira issue IDs from text.

        Args:
            text: Text to search for Jira issue identifiers

        Returns:
            List of Jira issue IDs found in text, normalized to uppercase format
        """
        # Match patterns like ABC-1234, abc-1234, SES 3456, ses 3456

        # Use word boundaries, require uppercase-style project codes (2-20 chars)
        # and reasonable issue numbers (1-6 digits)
        pattern = r"\b([A-Z]{2,20}[-\s]+\d{1,6})\b"
        matches = re.findall(pattern, text, re.IGNORECASE)

        # Normalize to uppercase format with dash separator
        normalized_ids = set()
        for match in matches:
            # Replace any whitespace with single dash and convert to uppercase
            normalized = re.sub(r"\s+", "-", match.strip()).upper()
            normalized_ids.add(normalized)

        return list(normalized_ids)

    async def update(self, issue_id: str, description: str) -> tuple[bool, str]:
        """Update Jira issue description.

        Args:
            issue_id: Issue key (e.g., 'PROJ-123')
            description: New description in Markdown format

        Returns:
            Tuple of (success: bool, message: str)
        """
        if self.config.get_use_mocks():
            return True, f"Mock: Would update {issue_id}"

        client = JiraClientService(self.config)
        return await client.update_description(issue_id, description)

    async def _fetch_issue(self, issue_id: str) -> JiraIssue:
        """Fetch issue from Jira API.

        Args:
            issue_id: Issue identifier (key like 'PROJ-123')

        Returns:
            JiraIssue instance with API data
        """
        email = self.config.get_email()
        token = self.config.get_token()

        # Use client service to get correct API base URL for token type
        jira_client = JiraClientService(self.config)
        base_url = await jira_client._get_api_base_url()
        url = f"{base_url}/issue/{issue_id}"

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
