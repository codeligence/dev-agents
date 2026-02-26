from typing import Any
import base64
import re

from pydantic_ai import Agent, BinaryContent
import httpx

from core.storage import BaseStorage

from .config import JiraConfig
from .markdown_to_adf import MarkdownToADFConverter
from .models import JiraIssue


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for use as cache key.

    Args:
        filename: Original filename

    Returns:
        Sanitized string with non-alphanumeric chars replaced by underscores
    """
    return re.sub(r"[^a-zA-Z0-9]", "_", filename)


IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".webp": "image/webp",
}


class JiraClientService:
    """Jira client service with helper functions for API interactions."""

    # Class-level cache for cloudId (shared across instances)
    _cloud_id_cache: str | None = None

    def __init__(self, config: JiraConfig):
        """Initialize with Jira configuration.

        Args:
            config: Jira configuration instance
        """
        self.config = config

    async def _get_cloud_id(self) -> str:
        """Discover and cache the Jira Cloud ID.

        The cloudId is required for the federated API URL. It's fetched
        from the tenant_info endpoint (no auth required) and cached.

        Returns:
            The Jira Cloud ID (UUID string)

        Raises:
            httpx.HTTPError: If the tenant_info request fails
        """
        if JiraClientService._cloud_id_cache is None:
            domain = self.config.get_domain()
            url = f"https://{domain}.atlassian.net/_edge/tenant_info"
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=10)
                resp.raise_for_status()
                JiraClientService._cloud_id_cache = resp.json()["cloudId"]
        return JiraClientService._cloud_id_cache

    async def _get_api_base_url(self) -> str:
        """Get the federated API base URL.

        Uses the federated URL pattern which works for all token types.

        Returns:
            Base URL for Jira REST API v3
        """
        cloud_id = await self._get_cloud_id()
        return f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3"

    async def _to_federated_url(self, url: str) -> str:
        """Convert a direct URL to federated URL.

        Attachment URLs from the API are direct domain URLs. They must
        be converted to federated URLs for API access.

        Args:
            url: Original URL (may be direct or already federated)

        Returns:
            URL using federated base
        """
        domain = self.config.get_domain()
        direct_base = f"https://{domain}.atlassian.net"

        if direct_base in url:
            cloud_id = await self._get_cloud_id()
            federated_base = f"https://api.atlassian.com/ex/jira/{cloud_id}"
            return url.replace(direct_base, federated_base)
        return url

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
        email = self.config.get_email()
        token = self.config.get_token()

        if not all([self.config.get_domain(), email, token]):
            print("Jira connection disabled: Missing configuration")
            return []

        base_url = await self._get_api_base_url()
        url = f"{base_url}/search"
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
    ) -> str:
        """Load all issues matching a JQL query and return formatted string.

        Args:
            jql_query: JQL query string
            max_results: Maximum results per request
            max_total_results: Maximum total results across all requests

        Returns:
            Formatted string of issues or error message
        """
        raw_issues = await self.download_issues_by_jql(
            jql_query, max_results, max_total_results
        )
        if not raw_issues:
            return "No issues found or error fetching issues."

        jira_issues = self.map_issues_to_jira_issues_model(raw_issues)
        return self.format_jira_issues(jira_issues, with_summary=True)

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

        # Convert to federated URL for API access
        url = await self._to_federated_url(attachment_url)

        auth = (str(email), str(token))
        headers = {"Accept": "*/*"}  # Accept any content type

        # Make the request to download the attachment (follow redirects)
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url, headers=headers, auth=auth, timeout=30, follow_redirects=True
            )

            if response.status_code == 200:
                # Read the content into memory
                content = response.content
                return True, content
            else:
                error_message = f"Failed to download attachment: {response.status_code}\n{response.text}"
                print(error_message)
                return False, error_message

    async def download_image_attachment_base64(
        self, attachment_url: str, filename: str
    ) -> str | None:
        """Download an attachment and return as base64 data URL if it's an image.

        Args:
            attachment_url: URL of the attachment to download
            filename: Filename of the attachment (used to determine MIME type)

        Returns:
            Base64 data URL string if successful and is image, None otherwise
        """
        # Get MIME type from filename extension
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        mime_type = IMAGE_MIME_TYPES.get(ext)
        if not mime_type:
            return None

        # Use the previously defined function to download the attachment bytes
        success, data = await self.download_attachment(attachment_url)

        if not success:
            print(f"Unable to download attachment from {attachment_url}")
            return None

        if isinstance(data, str):  # Error message
            return None

        # Base64 encode the image bytes
        base64_encoded = base64.b64encode(data).decode("utf-8")
        base64_image_url = f"data:{mime_type};base64,{base64_encoded}"

        return base64_image_url

    async def describe_image_attachment(
        self,
        url: str,
        filename: str,
        model: str,
        prompt: str,
    ) -> str | None:
        """Describe an image attachment using AI.

        Args:
            url: URL to the attachment
            filename: Filename of the attachment (used to determine MIME type)
            model: Model to use for description (e.g., 'openai:gpt-4o')
            prompt: Prompt for describing the image

        Returns:
            LLM response or None if URL is not an image or could not be downloaded
        """
        # Get MIME type from filename extension
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        mime_type = IMAGE_MIME_TYPES.get(ext)
        if not mime_type:
            return None

        # Download raw bytes
        success, data = await self.download_attachment(url)
        if not success or isinstance(data, str):
            return None

        # Use Pydantic AI agent for image description
        agent: Agent[None, str] = Agent(model=model, output_type=str)
        result = await agent.run(
            [prompt, BinaryContent(data=data, media_type=mime_type)]
        )
        return result.output

    async def describe_image_attachments_cached(
        self,
        issue: JiraIssue,
        model: str,
        storage: BaseStorage,
    ) -> dict[str, str]:
        """Describe all image attachments for an issue with caching.

        Args:
            issue: JiraIssue instance
            model: Model to use for description (e.g., 'openai:gpt-4o')
            storage: Storage instance for caching

        Returns:
            Dictionary mapping filename to description
        """
        descriptions: dict[str, str] = {}
        image_extensions = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp")

        issue_id = issue.get_key()
        attachments = issue.get_attachments()
        issue_context = issue.to_formatted_string(image_descriptions=None)

        for att in attachments:
            filename = att.get("filename", "")
            if not filename.lower().endswith(image_extensions):
                continue

            content_url = att.get("content", "")
            if not content_url:
                continue

            cache_key = f"jira_image_{issue_id}_{sanitize_filename(filename)}"

            # Check cache first
            cached = storage.get(cache_key)
            if cached:
                descriptions[filename] = cached
                continue

            # Describe and cache
            prompt = (
                "Describe this image concisely in the context of a Jira issue. "
                "Focus on what the image shows. "
                "It is an attachment of the following Jira issue:\n"
                f"{issue_context}"
            )
            description = await self.describe_image_attachment(
                content_url, filename, model, prompt
            )
            if description:
                storage.set(cache_key, description)
                descriptions[filename] = description

        return descriptions

    def format_jira_issues(
        self,
        issues: list[JiraIssue],
        with_summary: bool = True,
    ) -> str:
        """Format a list of Jira issues as a string.

        Args:
            issues: List of JiraIssue instances
            with_summary: Whether to include summaries

        Returns:
            Formatted string representation of all issues
        """
        formatted_strings = [
            issue.to_formatted_string(with_summary) for issue in issues
        ]
        return "\n".join(formatted_strings)

    async def update_description(
        self,
        issue_key: str,
        description: str,
        notify_users: bool = False,
    ) -> tuple[bool, str]:
        """Update an issue's description.

        The description is provided in Markdown format and automatically
        converted to Atlassian Document Format (ADF) for the API.

        Args:
            issue_key: Issue key (e.g., 'PROJ-123')
            description: Description in Markdown format
            notify_users: Whether to notify watchers (default: False)

        Returns:
            Tuple of (success: bool, message: str)
        """
        email = self.config.get_email()
        token = self.config.get_token()

        if not all([self.config.get_domain(), email, token]):
            return False, "Jira connection disabled: Missing configuration"

        converter = MarkdownToADFConverter()
        adf_description = converter.convert(description)

        base_url = await self._get_api_base_url()
        url = f"{base_url}/issue/{issue_key}"

        params: dict[str, str] = {}
        if not notify_users:
            params["notifyUsers"] = "false"

        payload = {"fields": {"description": adf_description}}

        auth = (str(email), str(token))
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.put(
                url,
                headers=headers,
                auth=auth,
                params=params,
                json=payload,
                timeout=30,
            )

            if response.status_code == 204:
                return True, f"Successfully updated description for {issue_key}"
            else:
                error_msg = (
                    f"Failed to update description: {response.status_code}\n"
                    f"{response.text}"
                )
                print(error_msg)
                return False, error_msg
