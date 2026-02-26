from typing import Any, cast

from bs4 import BeautifulSoup


class Person:
    """Represents a BitBucket user."""

    def __init__(self, data: dict[str, Any]):
        """Initialize with BitBucket API user data.

        Args:
            data: BitBucket API user data dictionary
        """
        self.data = data

    def get_display_name(self) -> str:
        """Get user's display name."""
        return cast("str", self.data.get("display_name", ""))

    def get_account_id(self) -> str:
        """Get user's account ID."""
        return cast("str", self.data.get("account_id", ""))

    def get_nickname(self) -> str:
        """Get user's nickname."""
        return cast("str", self.data.get("nickname", ""))

    def get_uuid(self) -> str:
        """Get user's UUID."""
        return cast("str", self.data.get("uuid", ""))

    def format(self) -> str:
        """Format person information as a string."""
        display_name = self.get_display_name()
        nickname = self.get_nickname()
        if nickname:
            return f"{display_name} (@{nickname})"
        return display_name


class PullRequest:
    """Represents a BitBucket pull request."""

    def __init__(self, pr_data: dict[str, Any], commits_data: list[dict[str, Any]]):
        """Initialize with BitBucket API pull request and commits data.

        Args:
            pr_data: BitBucket API pull request data dictionary
            commits_data: BitBucket API commits data list
        """
        self.pr_data = pr_data
        self.commits_data = commits_data

    def get_id(self) -> str:
        """Get pull request ID."""
        return str(self.pr_data.get("id", ""))

    def get_title(self) -> str:
        """Get pull request title."""
        return cast("str", self.pr_data.get("title", ""))

    def get_description(self) -> str:
        """Get pull request description."""
        return cast("str", self.pr_data.get("description", ""))

    def get_state(self) -> str:
        """Get pull request state (OPEN, MERGED, DECLINED, SUPERSEDED)."""
        return cast("str", self.pr_data.get("state", ""))

    def get_source_branch(self) -> str:
        """Get source branch name."""
        source = self.pr_data.get("source", {})
        branch = source.get("branch", {})
        return cast("str", branch.get("name", ""))

    def get_target_branch(self) -> str:
        """Get target branch name."""
        destination = self.pr_data.get("destination", {})
        branch = destination.get("branch", {})
        return cast("str", branch.get("name", ""))

    def get_source_commit_id(self) -> str:
        """Get source commit hash."""
        source = self.pr_data.get("source", {})
        commit = source.get("commit", {})
        return cast("str", commit.get("hash", ""))

    def get_target_commit_id(self) -> str:
        """Get target commit hash."""
        destination = self.pr_data.get("destination", {})
        commit = destination.get("commit", {})
        return cast("str", commit.get("hash", ""))

    def get_merge_commit_id(self) -> str | None:
        """Get merge commit hash (if merged)."""
        merge_commit = self.pr_data.get("merge_commit")
        if merge_commit:
            hash_value = merge_commit.get("hash")
            return cast("str", hash_value) if hash_value else None
        return None

    def get_author(self) -> Person:
        """Get the author of the pull request."""
        author_data = self.pr_data.get("author", {})
        return Person(author_data)

    def get_created_on(self) -> str:
        """Get creation date."""
        return cast("str", self.pr_data.get("created_on", ""))

    def get_updated_on(self) -> str:
        """Get last update date."""
        return cast("str", self.pr_data.get("updated_on", ""))

    def get_web_url(self) -> str:
        """Get web URL of the pull request."""
        links = self.pr_data.get("links", {})
        html_link = links.get("html", {})
        return cast("str", html_link.get("href", ""))

    def get_commits(self) -> list[dict[str, Any]]:
        """Get commits associated with the pull request."""
        return self.commits_data

    def get_plain_description(self) -> str:
        """Get plain text description (remove any HTML)."""
        description = self.get_description()
        if description:
            soup = BeautifulSoup(description, "html.parser")
            return soup.get_text()
        return ""

    def get_composed_PR_info(self) -> str:
        """Get composed pull request information for context."""
        author = self.get_author()
        author_name = author.format() if author else "Unknown"

        composed_info = f"Pull Request #{self.get_id()}: {self.get_title()}\n"
        composed_info += f"Author: {author_name}\n"
        composed_info += f"State: {self.get_state()}\n"
        composed_info += f"Source Branch: {self.get_source_branch()}\n"
        composed_info += f"Target Branch: {self.get_target_branch()}\n"
        composed_info += f"Created: {self.get_created_on()}\n"
        composed_info += f"Updated: {self.get_updated_on()}\n"

        web_url = self.get_web_url()
        if web_url:
            composed_info += f"URL: {web_url}\n"

        composed_info += f"\nDescription:\n{self.get_plain_description()}\n"

        composed_info += "\nCommits:\n"
        for commit in self.get_commits():
            sha = commit.get("hash", "")[:12]  # BitBucket uses 'hash' not 'sha'
            message = commit.get("message", "").split("\n")[0]  # First line only
            author_data = commit.get("author", {})
            commit_author = author_data.get("raw", "Unknown")
            composed_info += f"- {sha} ({commit_author}): {message}\n"

        return composed_info
