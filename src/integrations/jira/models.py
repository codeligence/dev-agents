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

from bs4 import BeautifulSoup


class JiraPerson:
    """Represents a Jira user from v3 API."""

    def __init__(self, data: dict[str, Any] | None):
        """Initialize with Jira API user data.

        Args:
            data: Jira API user data dictionary or None
        """
        self.data = data or {}

    def get_display_name(self) -> str:
        """Get user's display name."""
        return str(self.data.get("displayName", ""))

    def get_email(self) -> str:
        """Get user's email address."""
        return str(self.data.get("emailAddress", ""))

    def get_account_id(self) -> str:
        """Get user's account ID."""
        return str(self.data.get("accountId", ""))

    def get_name(self) -> str:
        """Get user's name (for backward compatibility)."""
        return self.get_display_name()


def format_attachments_v3(
    attachments: list[dict[str, Any]] | None, describe_images: bool = False
) -> str:
    """Format attachments for display (v3 API format).

    Args:
        attachments: List of attachment dictionaries
        describe_images: Whether to describe image attachments

    Returns:
        Formatted attachments string
    """
    if not attachments:
        return "None"

    lines = []
    image_extensions = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".svg")

    for att in attachments:
        filename = att.get("filename", "Unknown file")
        content_url = att.get("content", "")
        description = ""

        if describe_images and filename.lower().endswith(image_extensions):
            description = " [Image - description available via client service]"

        lines.append(f"  - {filename}: {content_url}{description}")

    return "\n".join(lines)


def format_comments_v3(comments_data: dict[str, Any] | None) -> str:
    """Format comments for display (v3 API format).

    Args:
        comments_data: Comments data from v3 API with structure:
                      {"comments": [...], "self": "...", "maxResults": N, "total": N}

    Returns:
        Formatted comments string
    """
    if not comments_data:
        return "None"

    comment_list = comments_data.get("comments", [])
    if not comment_list:
        return "None"

    lines = []
    for comment in comment_list:
        author_data = comment.get("author", {})
        author = author_data.get("displayName", "unknown") if author_data else "unknown"
        created = comment.get("created", "unknown date")

        # Handle v3 body format - could be string or complex object
        body = comment.get("body", "")
        if isinstance(body, dict):
            # If body is ADF format, extract text
            body = _extract_text_from_adf(body)
        elif isinstance(body, str):
            # If body is string, use as-is
            body = body
        else:
            body = str(body) if body else ""

        # Format body with proper indentation
        formatted_body = body.replace("\n", "\n      ") if body else ""
        lines.append(f"  - {author} on {created}:\n      {formatted_body}")

    return "\n".join(lines)


def format_subtasks_v3(subtasks: list[dict[str, Any]] | None) -> str:
    """Format subtasks for display (v3 API format).

    Args:
        subtasks: List of subtask dictionaries

    Returns:
        Formatted subtasks string
    """
    if not subtasks:
        return "None"

    lines = []
    for subtask in subtasks:
        key = subtask.get("key", "unknown")
        fields = subtask.get("fields", {})
        summary = fields.get("summary", "No summary") if fields else "No summary"
        lines.append(f"  - {key}: {summary}")

    return "\n".join(lines)


def format_linked_issues_v3(linked_issues: list[dict[str, Any]] | None) -> str:
    """Format linked issues for display (v3 API format).

    Args:
        linked_issues: List of issue link dictionaries

    Returns:
        Formatted linked issues string
    """
    if not linked_issues:
        return "None"

    lines = []
    for link in linked_issues:
        link_type_info = link.get("type", {})
        inward = link_type_info.get("inward")
        outward = link_type_info.get("outward")
        link_type_str = inward or outward or "Linked"

        issue = link.get("inwardIssue") or link.get("outwardIssue")
        if issue:
            issue_key = issue.get("key", "unknown")
            fields = issue.get("fields", {})
            summary = fields.get("summary", "No summary") if fields else ""
            lines.append(f"  - {link_type_str}: {issue_key} - {summary}")
        else:
            lines.append(f"  - {link_type_str}: No issue details found")

    return "\n".join(lines)


def format_changelog_v3(changelog: dict[str, Any] | None) -> str:
    """Format changelog for display (v3 API format).

    Args:
        changelog: Changelog dictionary from Jira v3 API

    Returns:
        Formatted changelog string
    """
    if not changelog or "histories" not in changelog:
        return "None"

    lines = []
    for history in changelog.get("histories", []):
        author_data = history.get("author", {})
        author = author_data.get("displayName", "unknown") if author_data else "unknown"
        created = history.get("created", "unknown date")
        lines.append(f"  - On {created} by {author}:")

        for item in history.get("items", []):
            field = item.get("field", "unknown field")
            from_val = item.get("fromString") or item.get("from") or "None"
            to_val = item.get("toString") or item.get("to") or "None"
            lines.append(f"      * {field}: {from_val} -> {to_val}")

    return "\n".join(lines)


def _extract_text_from_adf(adf_content: dict[str, Any]) -> str:
    """Extract plain text from Atlassian Document Format."""
    text_parts = []

    def extract_text_recursive(node: dict[str, Any] | list[Any] | Any) -> None:
        if isinstance(node, dict):
            # If this node has text, add it
            if "text" in node:
                text_parts.append(str(node["text"]))

            # Process content array if it exists
            if "content" in node and isinstance(node["content"], list):
                for child in node["content"]:
                    extract_text_recursive(child)
        elif isinstance(node, list):
            for item in node:
                extract_text_recursive(item)

    extract_text_recursive(adf_content)
    return " ".join(text_parts).strip()


class JiraIssue:
    """Represents a Jira issue from v3 API."""

    def __init__(self, issue_data: dict[str, Any]):
        """Initialize with Jira v3 API issue data.

        Args:
            issue_data: Jira v3 API issue data dictionary
        """
        self.issue_data = issue_data
        self.fields = issue_data.get("fields", {})

    def get_key(self) -> str:
        """Get issue key (e.g., 'PROJ-123')."""
        return str(self.issue_data.get("key", ""))

    def get_id(self) -> str:
        """Get issue ID."""
        return str(self.issue_data.get("id", ""))

    def get_summary(self) -> str:
        """Get issue summary."""
        return str(self.fields.get("summary", ""))

    def get_description(self) -> str:
        """Get issue description (v3 API format)."""
        description = self.fields.get("description")

        # Handle null description
        if description is None:
            return ""

        # Handle ADF format description
        if isinstance(description, dict):
            return _extract_text_from_adf(description)

        # Handle string description
        return str(description)

    def get_status(self) -> str:
        """Get issue status."""
        status_data = self.fields.get("status", {})
        return str(status_data.get("name", "")) if status_data else ""

    def get_priority(self) -> str:
        """Get issue priority."""
        priority_data = self.fields.get("priority", {})
        return str(priority_data.get("name", "")) if priority_data else ""

    def get_issue_type(self) -> str:
        """Get issue type."""
        issuetype_data = self.fields.get("issuetype", {})
        return str(issuetype_data.get("name", "")) if issuetype_data else ""

    def get_request_type(self) -> str:
        """Get request type (custom field)."""
        request_type_data = self.fields.get("customfield_10010")
        if request_type_data and isinstance(request_type_data, dict):
            return str(request_type_data.get("name", ""))
        return ""

    def get_creator(self) -> JiraPerson:
        """Get the creator of the issue."""
        creator_data = self.fields.get("creator")
        return JiraPerson(creator_data)

    def get_reporter(self) -> JiraPerson:
        """Get the reporter of the issue."""
        reporter_data = self.fields.get("reporter")
        return JiraPerson(reporter_data)

    def get_assignee(self) -> JiraPerson:
        """Get the assignee of the issue."""
        assignee_data = self.fields.get("assignee")
        return JiraPerson(assignee_data)

    def get_created_at(self) -> str:
        """Get creation timestamp."""
        return str(self.fields.get("created", ""))

    def get_updated_at(self) -> str:
        """Get last update timestamp."""
        return str(self.fields.get("updated", ""))

    def get_resolution_date(self) -> str | None:
        """Get resolution timestamp."""
        resolution_date = self.fields.get("resolutiondate")
        return str(resolution_date) if resolution_date is not None else None

    def get_attachments(self) -> list[dict[str, Any]]:
        """Get attachments list."""
        return self.fields.get("attachment", []) or []

    def get_comments(self) -> dict[str, Any]:
        """Get comments data (v3 format)."""
        return self.fields.get("comment", {}) or {}

    def get_subtasks(self) -> list[dict[str, Any]]:
        """Get subtasks list."""
        return self.fields.get("subtasks", []) or []

    def get_linked_issues(self) -> list[dict[str, Any]]:
        """Get linked issues list."""
        return self.fields.get("issuelinks", []) or []

    def get_changelog(self) -> dict[str, Any]:
        """Get changelog dictionary."""
        return self.issue_data.get("changelog", {}) or {}

    def get_html_description(self) -> str:
        """Get HTML description."""
        return self.get_description()

    def get_plain_description(self) -> str:
        """Get plain text description (remove any HTML/markup)."""
        html_desc = self.get_html_description()
        if html_desc and isinstance(html_desc, str):
            try:
                soup = BeautifulSoup(html_desc, "html.parser")
                return soup.get_text()
            except Exception:
                return html_desc
        return ""

    def get_web_url(self) -> str:
        """Get web URL of the issue."""
        # This should be constructed using the actual domain from config
        # For now, using placeholder
        return f"https://example.atlassian.net/browse/{self.get_key()}"

    def to_formatted_string(
        self, with_summary: bool = True, describe_images: bool = False
    ) -> str:
        """Get formatted string representation of the issue.

        Args:
            with_summary: Whether to include the summary in the output
            describe_images: Whether to describe image attachments

        Returns:
            Formatted issue information
        """
        summary_str = f"Summary: {self.get_summary()}\n" if with_summary else ""

        creator = self.get_creator()
        reporter = self.get_reporter()
        assignee = self.get_assignee()

        creator_name = creator.get_display_name() or "Unknown"
        reporter_name = reporter.get_display_name() or "Unknown"
        assignee_name = assignee.get_display_name() or "Unassigned"

        additional_info = (
            "Additional Info:\n"
            f"  Reporter: {reporter_name}\n"
            f"  Status: {self.get_status()}\n"
            f"  Priority: {self.get_priority()}\n"
            f"  Issue Type: {self.get_issue_type()}\n"
            f"  Request Type: {self.get_request_type()}\n"
            f"  Created: {self.get_created_at()}\n"
            f"  Updated: {self.get_updated_at()}\n"
            f"  Resolution Date: {self.get_resolution_date()}\n"
        )

        return (
            f"Link: {self.get_web_url()}\n"
            f"Issue: {self.get_key()}\n"
            f"{summary_str}"
            f"Creator: {creator_name}\n"
            f"Assignee: {assignee_name}\n"
            f"Description: {self.get_plain_description()}\n\n"
            f"{additional_info}\n"
            f"Attachments:\n{format_attachments_v3(self.get_attachments(), describe_images)}\n\n"
            f"Comments:\n{format_comments_v3(self.get_comments())}\n\n"
            f"Subtasks:\n{format_subtasks_v3(self.get_subtasks())}\n\n"
            f"Linked Issues:\n{format_linked_issues_v3(self.get_linked_issues())}\n"
        )

    def get_composed_issue_info(self) -> str:
        """Get composed issue information for AI context."""
        return self.to_formatted_string(with_summary=True, describe_images=False)
