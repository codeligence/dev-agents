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
import base64

import httpx

try:
    import magic  # type: ignore
except ImportError:
    magic = None

from .config import JiraConfig
from .models import JiraIssue


class JiraClientService:
    """Jira client service with helper functions for API interactions."""

    def __init__(self, config: JiraConfig):
        """Initialize with Jira configuration.

        Args:
            config: Jira configuration instance
        """
        self.config = config

    def create_issue_link(self, key: str | None) -> str:
        """Create issue URL from issue key.

        Args:
            key: Issue key (e.g., 'PROJ-123')

        Returns:
            Issue URL or 'unknown' if key/domain missing
        """
        domain = self.config.get_domain()
        if not domain or not key:
            return "unknown"
        return f"https://{domain}.atlassian.net/browse/{key}"

    async def download_issues_by_jql(
        self, jql_query: str, max_results: int = 100, max_total_results: int = 99999
    ) -> list[dict[str, Any]]:
        """Load all issues matching a JQL query.

        Args:
            jql_query: JQL query string
            max_results: Maximum results per request
            max_total_results: Maximum total results across all requests

        Returns:
            List of issue dictionaries from Jira API
        """
        domain = self.config.get_domain()
        email = self.config.get_email()
        token = self.config.get_token()

        if not all([domain, email, token]):
            print("Jira connection disabled: Missing configuration")
            return []

        url = f"https://{domain}.atlassian.net/rest/api/3/search"
        auth = (str(email), str(token))
        headers = {"Accept": "application/json"}

        start_at = 0
        all_issues = []

        async with httpx.AsyncClient() as client:
            while True:
                params: dict[str, str | int] = {
                    "jql": jql_query,
                    "startAt": start_at,
                    "maxResults": max_results,
                    "fields": "*all",
                    "expand": "changelog",
                }

                response = await client.get(
                    url, headers=headers, auth=auth, params=params, timeout=30
                )

                if response.status_code != 200:
                    print(f"Failed to fetch issues: {response.status_code}")
                    print(response.text)
                    return []

                response_data = response.json()
                issues = response_data.get("issues", [])
                all_issues.extend(issues)

                if start_at + max_results >= response_data.get("total", 0):
                    break
                if start_at + max_results >= max_total_results:
                    break
                if len(issues) == 0:
                    # Don't keep going if there are no new issues
                    break

                start_at += max_results

        return all_issues

    def map_issue_to_jira_issue_model(self, issue: dict[str, Any]) -> JiraIssue:
        """Map raw API issue data to JiraIssue model.

        Args:
            issue: Raw issue dictionary from Jira API

        Returns:
            JiraIssue model instance
        """
        return JiraIssue(issue)

    def map_issues_to_jira_issues_model(
        self, issues: list[dict[str, Any]]
    ) -> list[JiraIssue]:
        """Map list of raw API issues to JiraIssue models.

        Args:
            issues: List of raw issue dictionaries from Jira API

        Returns:
            List of JiraIssue model instances
        """
        return [self.map_issue_to_jira_issue_model(issue) for issue in issues]

    async def get_issues_by_jql(
        self,
        jql_query: str,
        max_results: int = 100,
        max_total_results: int = 99999,
        describe_images: bool = False,
    ) -> str:
        """Load all issues matching a JQL query and return formatted string.

        Args:
            jql_query: JQL query string
            max_results: Maximum results per request
            max_total_results: Maximum total results across all requests
            describe_images: Whether to describe image attachments

        Returns:
            Formatted string of issues or error message
        """
        raw_issues = await self.download_issues_by_jql(
            jql_query, max_results, max_total_results
        )
        if not raw_issues:
            return "No issues found or error fetching issues."

        jira_issues = self.map_issues_to_jira_issues_model(raw_issues)
        return self.format_jira_issues(
            jira_issues, describe_images=describe_images, with_summary=True
        )

    async def download_attachment(
        self, attachment_url: str
    ) -> tuple[bool, bytes | str]:
        """Download an attachment from the given URL.

        Args:
            attachment_url: URL of the attachment to download

        Returns:
            Tuple of (success: bool, content: bytes | error_message: str)
        """
        email = self.config.get_email()
        token = self.config.get_token()

        if not email or not token:
            error_message = (
                "Jira connection disabled: Missing email or token configuration"
            )
            print(error_message)
            return False, error_message

        auth = (str(email), str(token))
        headers = {"Accept": "*/*"}  # Accept any content type

        # Make the request to download the attachment
        async with httpx.AsyncClient() as client:
            response = await client.get(
                attachment_url, headers=headers, auth=auth, timeout=30
            )

            if response.status_code == 200:
                # Read the content into memory
                content = response.content
                return True, content
            else:
                error_message = f"Failed to download attachment: {response.status_code}\n{response.text}"
                print(error_message)
                return False, error_message

    async def download_image_attachment_base64(self, attachment_url: str) -> str | None:
        """Download an attachment and return as base64 data URL if it's an image.

        Args:
            attachment_url: URL of the attachment to download

        Returns:
            Base64 data URL string if successful and is image, None otherwise
        """
        # Use the previously defined function to download the attachment bytes
        success, data = await self.download_attachment(attachment_url)

        if not success:
            print(f"Unable to download attachment from {attachment_url}")
            return None

        if isinstance(data, str):  # Error message
            return None

        # Check the MIME type using python-magic
        if magic is None:
            print(
                f"python-magic not available, cannot determine MIME type for {attachment_url}"
            )
            return None

        mime = magic.Magic(mime=True)
        mime_type = mime.from_buffer(data)
        if not mime_type.startswith("image/"):
            print(
                f"Downloaded file from {attachment_url} is not a recognized image format."
            )
            return None

        # Base64 encode the image bytes
        base64_encoded = base64.b64encode(data).decode("utf-8")
        base64_image_url = f"data:{mime_type};base64,{base64_encoded}"

        return base64_image_url

    async def describe_image_attachment(
        self, url: str, describe_prompt: str, model: str = "Haiku"
    ) -> str | None:
        """Describe an image attachment using AI.

        Args:
            url: URL to the attachment
            describe_prompt: Prompt for describing the image
            model: Model to use for description (default: "Haiku")

        Returns:
            LLM response or None if URL is not an image or could not be downloaded
        """
        url_encoded_image = await self.download_image_attachment_base64(url)

        if url_encoded_image is None:
            # Attachment is not an image
            return None

        # Note: This would require integrating with the LLM service
        # For now, returning a placeholder that indicates functionality exists
        return f"[Image description would be generated here using {model} with prompt: {describe_prompt}]"

    def format_jira_issues(
        self,
        issues: list[JiraIssue],
        with_summary: bool = True,
        describe_images: bool = False,
    ) -> str:
        """Format a list of Jira issues as a string.

        Args:
            issues: List of JiraIssue instances
            with_summary: Whether to include summaries
            describe_images: Whether to describe image attachments

        Returns:
            Formatted string representation of all issues
        """
        formatted_strings = [
            issue.to_formatted_string(with_summary, describe_images) for issue in issues
        ]
        return "\n".join(formatted_strings)
