from typing import Any, cast

from bs4 import BeautifulSoup


class Person:
    """Represents a GitLab user."""

    def __init__(self, data: dict[str, Any]):
        """Initialize with GitLab API user data.

        Args:
            data: GitLab API user data dictionary
        """
        self.data = data

    def get_name(self) -> str:
        """Get user's full name."""
        return cast("str", self.data.get("name", ""))

    def get_username(self) -> str:
        """Get user's username."""
        return cast("str", self.data.get("username", ""))

    def get_id(self) -> int:
        """Get user's ID."""
        return cast("int", self.data.get("id", 0))


class MergeRequest:
    """Represents a GitLab merge request."""

    def __init__(self, mr_data: dict[str, Any], commits_data: list[dict[str, Any]]):
        """Initialize with GitLab API merge request and commits data.

        Args:
            mr_data: GitLab API merge request data dictionary
            commits_data: GitLab API commits data list
        """
        self.mr_data = mr_data
        self.commits_data = commits_data

    def get_id(self) -> str:
        """Get merge request ID."""
        return str(self.mr_data.get("iid", ""))

    def get_title(self) -> str:
        """Get merge request title."""
        return cast("str", self.mr_data.get("title", ""))

    def get_description(self) -> str:
        """Get merge request description."""
        return cast("str", self.mr_data.get("description", ""))

    def get_state(self) -> str:
        """Get merge request state."""
        return cast("str", self.mr_data.get("state", ""))

    def get_source_branch(self) -> str:
        """Get source branch name."""
        return cast("str", self.mr_data.get("source_branch", ""))

    def get_target_branch(self) -> str:
        """Get target branch name."""
        return cast("str", self.mr_data.get("target_branch", ""))

    def get_author(self) -> Person:
        """Get the author of the merge request."""
        author_data = self.mr_data.get("author", {})
        return Person(author_data)

    def get_merge_commit_id(self) -> str | None:
        """Get merge commit SHA."""
        return self.mr_data.get("merge_commit_sha")

    def get_source_commit_id(self) -> str:
        """Get source commit SHA."""
        return cast("str", self.mr_data.get("sha", ""))

    def get_target_commit_id(self) -> str | None:
        """Get target commit SHA from diff_refs."""
        diff_refs = self.mr_data.get("diff_refs", {})
        return diff_refs.get("base_sha") if diff_refs else None

    def get_created_at(self) -> str:
        """Get creation date."""
        return cast("str", self.mr_data.get("created_at", ""))

    def get_updated_at(self) -> str:
        """Get last update date."""
        return cast("str", self.mr_data.get("updated_at", ""))

    def get_merged_at(self) -> str | None:
        """Get merge date."""
        return self.mr_data.get("merged_at")

    def get_commits(self) -> list[dict[str, Any]]:
        """Get commits associated with the merge request."""
        return self.commits_data

    def get_html_description(self) -> str:
        """Get HTML description."""
        # In a real implementation, this would convert markdown to HTML
        return self.get_description()

    def get_plain_description(self) -> str:
        """Get plain text description (remove any HTML)."""
        html_desc = self.get_html_description()
        if html_desc:
            # Use BeautifulSoup to strip HTML tags
            soup = BeautifulSoup(html_desc, "html.parser")
            return soup.get_text()
        return ""

    def get_web_url(self) -> str:
        """Get web URL of the merge request."""
        return cast("str", self.mr_data.get("web_url", ""))

    def get_composed_MR_info(self) -> str:
        """Get composed merge request information for context."""
        author = self.get_author()
        author_name = (
            f"{author.get_name()} (@{author.get_username()})" if author else "Unknown"
        )

        composed_info = f"Merge Request #{self.get_id()}: {self.get_title()}\n"
        composed_info += f"Author: {author_name}\n"
        composed_info += f"State: {self.get_state()}\n"
        composed_info += f"Source Branch: {self.get_source_branch()}\n"
        composed_info += f"Target Branch: {self.get_target_branch()}\n"
        composed_info += f"Created: {self.get_created_at()}\n"
        composed_info += f"Updated: {self.get_updated_at()}\n"

        if self.get_merged_at():
            composed_info += f"Merged: {self.get_merged_at()}\n"

        composed_info += f"\nDescription:\n{self.get_plain_description()}\n"

        composed_info += "\nCommits:\n"
        for commit in self.get_commits():
            sha = commit.get("id", "")[:8]
            message = commit.get("title", "")
            author = commit.get("author_name", "")
            composed_info += f"- {sha} ({author}): {message}\n"

        return composed_info


class Issue:
    """Represents a GitLab issue."""

    def __init__(self, issue_data: dict[str, Any]):
        """Initialize with GitLab API issue data.

        Args:
            issue_data: GitLab API issue data dictionary
        """
        self.issue_data = issue_data

    def get_id(self) -> str:
        """Get issue ID."""
        return str(self.issue_data.get("iid", ""))

    def get_title(self) -> str:
        """Get issue title."""
        return cast("str", self.issue_data.get("title", ""))

    def get_description(self) -> str:
        """Get issue description."""
        return cast("str", self.issue_data.get("description", ""))

    def get_state(self) -> str:
        """Get issue state."""
        return cast("str", self.issue_data.get("state", ""))

    def get_author(self) -> Person:
        """Get the author of the issue."""
        author_data = self.issue_data.get("author", {})
        return Person(author_data)

    def get_created_at(self) -> str:
        """Get creation date."""
        return cast("str", self.issue_data.get("created_at", ""))

    def get_updated_at(self) -> str:
        """Get last update date."""
        return cast("str", self.issue_data.get("updated_at", ""))

    def get_closed_at(self) -> str | None:
        """Get close date."""
        return self.issue_data.get("closed_at")

    def get_html_description(self) -> str:
        """Get HTML description."""
        # In a real implementation, this would convert markdown to HTML
        return self.get_description()

    def get_plain_description(self) -> str:
        """Get plain text description (remove any HTML)."""
        html_desc = self.get_html_description()
        if html_desc:
            # Use BeautifulSoup to strip HTML tags
            soup = BeautifulSoup(html_desc, "html.parser")
            return soup.get_text()
        return ""

    def get_web_url(self) -> str:
        """Get web URL of the issue."""
        return cast("str", self.issue_data.get("web_url", ""))

    def get_composed_issue_info(self) -> str:
        """Get composed issue information for context."""
        author = self.get_author()
        author_name = (
            f"{author.get_name()} (@{author.get_username()})" if author else "Unknown"
        )

        composed_info = f"Issue #{self.get_id()}: {self.get_title()}\n"
        composed_info += f"Author: {author_name}\n"
        composed_info += f"State: {self.get_state()}\n"
        composed_info += f"Created: {self.get_created_at()}\n"
        composed_info += f"Updated: {self.get_updated_at()}\n"

        if self.get_closed_at():
            composed_info += f"Closed: {self.get_closed_at()}\n"

        composed_info += f"\nDescription:\n{self.get_plain_description()}\n"

        return composed_info


class Pipeline:
    """Represents a GitLab pipeline."""

    def __init__(
        self,
        pipeline_data: dict[str, Any],
        jobs_data: list[dict[str, Any]] | None = None,
    ):
        """Initialize with GitLab API pipeline and jobs data.

        Args:
            pipeline_data: GitLab API pipeline data dictionary
            jobs_data: Optional GitLab API jobs data list
        """
        self.pipeline_data = pipeline_data
        self.jobs_data = jobs_data or []

    def get_id(self) -> str:
        """Get pipeline ID."""
        return str(self.pipeline_data.get("id", ""))

    def get_iid(self) -> str:
        """Get pipeline IID (internal ID)."""
        return str(self.pipeline_data.get("iid", ""))

    def get_status(self) -> str:
        """Get pipeline status."""
        return cast("str", self.pipeline_data.get("status", ""))

    def get_ref(self) -> str:
        """Get git reference (branch/tag)."""
        return cast("str", self.pipeline_data.get("ref", ""))

    def get_sha(self) -> str:
        """Get commit SHA."""
        return cast("str", self.pipeline_data.get("sha", ""))

    def get_created_at(self) -> str:
        """Get creation date."""
        return cast("str", self.pipeline_data.get("created_at", ""))

    def get_updated_at(self) -> str:
        """Get last update date."""
        return cast("str", self.pipeline_data.get("updated_at", ""))

    def get_finished_at(self) -> str | None:
        """Get finish date."""
        return self.pipeline_data.get("finished_at")

    def get_duration(self) -> int | None:
        """Get pipeline duration in seconds."""
        return self.pipeline_data.get("duration")

    def get_web_url(self) -> str:
        """Get web URL of the pipeline."""
        return cast("str", self.pipeline_data.get("web_url", ""))

    def get_jobs(self) -> list[dict[str, Any]]:
        """Get jobs associated with the pipeline."""
        return self.jobs_data

    def get_failed_jobs(self) -> list[dict[str, Any]]:
        """Get only failed jobs."""
        return [job for job in self.jobs_data if job.get("status") == "failed"]

    def get_user(self) -> dict[str, Any] | None:
        """Get user who triggered the pipeline."""
        return self.pipeline_data.get("user")

    def get_source(self) -> str:
        """Get pipeline source (push, merge_request_event, etc.)."""
        return cast("str", self.pipeline_data.get("source", ""))

    def get_merge_request(self) -> dict[str, Any] | None:
        """Get merge request info if pipeline was triggered by MR."""
        return self.pipeline_data.get("merge_request")

    def get_before_sha(self) -> str:
        """Get the commit SHA before this pipeline."""
        return cast("str", self.pipeline_data.get("before_sha", ""))

    def get_coverage(self) -> str | None:
        """Get code coverage percentage."""
        return self.pipeline_data.get("coverage")

    def get_composed_pipeline_info(self) -> str:
        """Get composed pipeline information for context."""
        # Header
        composed_info = "=" * 80 + "\n"
        composed_info += f"📊 PIPELINE #{self.get_iid()} (ID: {self.get_id()})\n"
        composed_info += "=" * 80 + "\n\n"

        # Status
        status = self.get_status()
        status_emoji = {
            "success": "✅",
            "failed": "❌",
            "running": "🔄",
            "pending": "⏳",
            "canceled": "🚫",
            "skipped": "⏭️",
        }.get(status, "❓")
        composed_info += f"Status: {status_emoji} {status.upper()}\n"

        # Reference & Commit
        composed_info += f"Branch/Tag: {self.get_ref()}\n"
        composed_info += f"Commit SHA: {self.get_sha()}\n"
        if self.get_before_sha():
            composed_info += f"Previous SHA: {self.get_before_sha()}\n"

        # Triggered by
        user = self.get_user()
        if user:
            username = user.get("username", "Unknown")
            name = user.get("name", username)
            composed_info += f"Triggered by: {name} (@{username})\n"

        # Source
        source = self.get_source()
        composed_info += f"Source: {source}\n"

        # Merge Request info
        mr = self.get_merge_request()
        if mr:
            mr_iid = mr.get("iid", "?")
            mr_title = mr.get("title", "")
            composed_info += f"Merge Request: !{mr_iid} - {mr_title}\n"

        # Timing
        composed_info += "\n⏱️ Timing:\n"
        composed_info += f"  Created: {self.get_created_at()}\n"
        composed_info += f"  Updated: {self.get_updated_at()}\n"
        if self.get_finished_at():
            composed_info += f"  Finished: {self.get_finished_at()}\n"

        duration = self.get_duration()
        if duration:
            duration_mins = duration // 60
            duration_secs = duration % 60
            composed_info += f"  Duration: {duration_mins}m {duration_secs}s\n"

        # Coverage
        coverage = self.get_coverage()
        if coverage:
            composed_info += f"\n📈 Code Coverage: {coverage}%\n"

        # Web URL
        composed_info += f"\n🔗 Web URL: {self.get_web_url()}\n"

        # Jobs Summary
        if self.jobs_data:
            composed_info += "\n" + "=" * 80 + "\n"
            composed_info += f"📋 JOBS ({len(self.jobs_data)} total)\n"
            composed_info += "=" * 80 + "\n\n"

            # Group jobs by stage
            stages: dict[str, list[dict[str, Any]]] = {}
            for job in self.jobs_data:
                stage = job.get("stage", "unknown")
                if stage not in stages:
                    stages[stage] = []
                stages[stage].append(job)

            # Show jobs by stage
            for stage, jobs in stages.items():
                composed_info += f"\n🔹 Stage: {stage}\n"
                for job in jobs:
                    job_id = job.get("id", "")
                    job_name = job.get("name", "")
                    job_status = job.get("status", "")

                    job_status_emoji = {
                        "success": "✅",
                        "failed": "❌",
                        "running": "🔄",
                        "pending": "⏳",
                        "canceled": "🚫",
                        "skipped": "⏭️",
                    }.get(job_status, "❓")

                    composed_info += (
                        f"  {job_status_emoji} [{job_status}] {job_name} "
                        f"(ID: {job_id})\n"
                    )

                    # Add duration if available
                    job_duration = job.get("duration")
                    if job_duration:
                        mins = int(job_duration) // 60
                        secs = int(job_duration) % 60
                        composed_info += f"     Duration: {mins}m {secs}s\n"

                    # Add failure reason if job failed
                    if job_status == "failed":
                        failure_reason = job.get("failure_reason", "Unknown")
                        composed_info += f"     ⚠️ Failure Reason: {failure_reason}\n"

        # Failed jobs summary
        failed_jobs = self.get_failed_jobs()
        if failed_jobs:
            composed_info += "\n" + "=" * 80 + "\n"
            composed_info += f"❌ FAILED JOBS ({len(failed_jobs)})\n"
            composed_info += "=" * 80 + "\n\n"
            for job in failed_jobs:
                job_name = job.get("name", "")
                job_id = job.get("id", "")
                failure_reason = job.get("failure_reason", "Unknown")
                composed_info += f"• {job_name} (ID: {job_id})\n"
                composed_info += f"  Reason: {failure_reason}\n\n"

        return composed_info
