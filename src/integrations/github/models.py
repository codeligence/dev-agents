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


from typing import Any, cast
import re

from bs4 import BeautifulSoup


class GitHubError(Exception):
    """Exception raised for GitHub-specific errors."""

    pass


class Person:
    """Represents a GitHub user."""

    def __init__(self, display_name: str, login: str):
        """Initialize with GitHub user data.

        Args:
            display_name: User's display name
            login: User's login/username
        """
        self.display_name = display_name
        self.login = login

    def format(self) -> str:
        """Format person information as a string."""
        return f"{self.display_name} <{self.login}>"


class Issue:
    """Represents a GitHub issue."""

    def __init__(
        self,
        response_json: dict[str, Any],
        comments_data: list[dict[str, Any]] | None = None,
    ):
        """Initialize with GitHub API issue data.

        Args:
            response_json: GitHub API issue data dictionary
            comments_data: GitHub API comments data list (optional)
        """
        self.data = response_json
        self.comments_data = comments_data or []

    def get_number(self) -> int:
        """Get issue number."""
        return cast("int", self.data.get("number", 0))

    def get_title(self) -> str:
        """Get issue title."""
        return cast("str", self.data.get("title", ""))

    def get_state(self) -> str:
        """Get issue state."""
        return cast("str", self.data.get("state", ""))

    def get_created_at(self) -> str:
        """Get creation date."""
        return cast("str", self.data.get("created_at", ""))

    def get_updated_at(self) -> str:
        """Get last update date."""
        return cast("str", self.data.get("updated_at", ""))

    def get_closed_at(self) -> str | None:
        """Get close date."""
        return self.data.get("closed_at")

    def get_creator(self) -> Person:
        """Get the creator of the issue."""
        user = self.data.get("user", {})
        return Person(
            display_name=user.get("name", user.get("login", "")),
            login=user.get("login", ""),
        )

    def get_assignee(self) -> Person | None:
        """Get the assignee of the issue."""
        assignee = self.data.get("assignee")
        if assignee:
            return Person(
                display_name=assignee.get("name", assignee.get("login", "")),
                login=assignee.get("login", ""),
            )
        return None

    def get_body(self) -> str:
        """Get issue body."""
        return cast("str", self.data.get("body", ""))

    def get_body_plain(self) -> str:
        """Return the issue body with markdown formatting removed.

        Returns:
            Plain text description without markdown formatting
        """
        body = self.get_body()
        if not body:
            return ""

        # Use BeautifulSoup to parse HTML (for any HTML in the markdown)
        soup = BeautifulSoup(body, "html.parser")

        # Extract text
        clean_text = soup.get_text(separator=" ", strip=True)

        # Remove extra whitespace
        clean_text = re.sub(r"\s+", " ", clean_text).strip()

        return clean_text

    def get_labels(self) -> list[str]:
        """Get issue labels."""
        return [label.get("name", "") for label in self.data.get("labels", [])]

    def get_milestone(self) -> str | None:
        """Get issue milestone."""
        milestone = self.data.get("milestone")
        if milestone:
            title = milestone.get("title", "")
            return str(title) if title else None
        return None

    def get_pull_request_urls(self) -> list[str]:
        """Get associated pull request URLs."""
        pr_links = self.data.get("pull_request", {})
        if pr_links:
            return [pr_links.get("url", "")]
        return []

    def get_comments(self) -> list[dict[str, Any]]:
        """Get issue comments."""
        return self.comments_data

    def get_formatted_comments(self) -> str:
        """Get formatted comments as a string."""
        if not self.comments_data:
            return ""

        comments_text = "\nComments:\n"
        for i, comment in enumerate(self.comments_data, 1):
            user = comment.get("user", {})
            author = Person(
                display_name=user.get("name", user.get("login", "")),
                login=user.get("login", ""),
            )
            created_at = comment.get("created_at", "")
            body = comment.get("body", "")

            # Use BeautifulSoup to clean markdown/HTML from comment body
            if body:
                soup = BeautifulSoup(body, "html.parser")
                clean_body = soup.get_text(separator=" ", strip=True)
                clean_body = re.sub(r"\s+", " ", clean_body).strip()
            else:
                clean_body = ""

            comments_text += f"Comment #{i} by {author.format()} at {created_at}:\n"
            comments_text += f"{clean_body}\n\n"

        return comments_text

    def get_composed_issue_info(self) -> str:
        """Return a formatted string with all issue information."""
        info = f"Title: {self.get_title()}\n"
        info += f"Number: #{self.get_number()}\n"
        info += f"State: {self.get_state()}\n"
        info += f"Created At: {self.get_created_at()}\n"
        info += f"Updated At: {self.get_updated_at()}\n"

        closed_at = self.get_closed_at()
        if closed_at:
            info += f"Closed At: {closed_at}\n"

        info += f"Creator: {self.get_creator().format()}\n"

        assignee = self.get_assignee()
        if assignee:
            info += f"Assignee: {assignee.format()}\n"

        labels = self.get_labels()
        if labels:
            info += f"Labels: {', '.join(labels)}\n"

        milestone = self.get_milestone()
        if milestone:
            info += f"Milestone: {milestone}\n"

        info += f"Description: {self.get_body_plain()}\n"

        # Add comments if available
        comments = self.get_formatted_comments()
        if comments:
            info += comments

        return info


class PullRequest:
    """Represents a GitHub pull request."""

    def __init__(self, pr_data: dict[str, Any], commit_data: list[dict[str, Any]]):
        """Initialize with GitHub API pull request and commits data.

        Args:
            pr_data: GitHub API pull request data dictionary
            commit_data: GitHub API commits data list
        """
        self.pr = pr_data
        self.commit_data = commit_data

    def get_number(self) -> int:
        """Get pull request number."""
        return cast("int", self.pr.get("number", 0))

    def get_title(self) -> str:
        """Get pull request title."""
        return cast("str", self.pr.get("title", ""))

    def get_state(self) -> str:
        """Get pull request state."""
        return cast("str", self.pr.get("state", ""))

    def get_created_at(self) -> str:
        """Get creation date."""
        return cast("str", self.pr.get("created_at", ""))

    def get_updated_at(self) -> str:
        """Get last update date."""
        return cast("str", self.pr.get("updated_at", ""))

    def get_closed_at(self) -> str | None:
        """Get close date."""
        return self.pr.get("closed_at")

    def get_merged_at(self) -> str | None:
        """Get merge date."""
        return self.pr.get("merged_at")

    def get_creator(self) -> Person:
        """Get the creator of the pull request."""
        user = self.pr.get("user", {})
        return Person(
            display_name=user.get("name", user.get("login", "")),
            login=user.get("login", ""),
        )

    def get_source_branch(self) -> str:
        """Get the source branch name."""
        return cast("str", self.pr.get("head", {}).get("ref", ""))

    def get_target_branch(self) -> str:
        """Get the target branch name."""
        return cast("str", self.pr.get("base", {}).get("ref", ""))

    def get_source_commit_id(self) -> str:
        """Get the commit ID of the head commit."""
        return cast("str", self.pr.get("head", {}).get("sha", ""))

    def get_target_commit_id(self) -> str:
        """Get the commit ID of the base commit."""
        return cast("str", self.pr.get("base", {}).get("sha", ""))

    def get_merge_commit_id(self) -> str:
        """Get the commit ID of the merge commit, if merged."""
        return cast("str", self.pr.get("merge_commit_sha", ""))

    def get_commit_hashes(self) -> list[str]:
        """Get all commit hashes included in the PR."""
        return [commit.get("sha", "") for commit in self.commit_data]

    def get_composed_PR_info(self) -> str:
        """Return a formatted string with all pull request information."""
        info = f"Pull Request Number: #{self.get_number()}\n"
        info += f"Title: {self.get_title()}\n"
        info += f"State: {self.get_state()}\n"
        info += f"Created By: {self.get_creator().format()}\n"
        info += f"Creation Date: {self.get_created_at()}\n"

        closed_at = self.get_closed_at()
        if closed_at:
            info += f"Closed Date: {closed_at}\n"

        merged_at = self.get_merged_at()
        if merged_at:
            info += f"Merged Date: {merged_at}\n"

        info += f"Source Branch: {self.get_source_branch()}\n"
        info += f"Target Branch: {self.get_target_branch()}\n"

        return info
