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
import base64
import urllib.parse

import httpx

from core.protocols.provider_protocols import (
    IssueModel,
    IssueProvider,
    PullRequestModel,
    PullRequestProvider,
)

from .config import GitHubConfig
from .mock_github import mock_fetch_issue_with_comments, mock_fetch_pull_request
from .models import Issue, PullRequest


class GitHubPullRequestProvider(PullRequestProvider):
    """GitHub implementation of PullRequestProvider."""

    def __init__(self, config: GitHubConfig):
        self.config = config

    @staticmethod
    def from_config(
        config_data: dict[str, Any],
    ) -> Optional["GitHubPullRequestProvider"]:
        """Create provider from configuration data.

        Args:
            config_data: GitHub configuration dictionary

        Returns:
            Provider instance if config is valid, None otherwise
        """
        config = GitHubConfig.from_config_data(config_data)
        if not config.is_configured():
            return None
        return GitHubPullRequestProvider(config)

    async def load(self, pull_request_id: str) -> PullRequestModel:
        """Load pull request by ID.

        Args:
            pull_request_id: Pull request identifier

        Returns:
            PullRequestModel with id and context
        """
        if self.config.get_use_mocks():
            pr_data = mock_fetch_pull_request(pull_request_id)
            context = pr_data.get_composed_PR_info()
            source_branch = pr_data.get_source_branch()
            target_branch = pr_data.get_target_branch()
            source_refs = self._get_source_refs(pr_data)
            target_refs = self._get_target_refs(pr_data)
        else:
            pr_data = await self._fetch_pull_request(pull_request_id)
            context = pr_data.get_composed_PR_info()
            source_branch = pr_data.get_source_branch()
            target_branch = pr_data.get_target_branch()
            source_refs = self._get_source_refs(pr_data)
            target_refs = self._get_target_refs(pr_data)

        return PullRequestModel(
            id=pull_request_id,
            context=context,
            source_branch=source_branch,
            target_branch=target_branch,
            source_refs=source_refs,
            target_refs=target_refs,
        )

    def _get_source_refs(self, pr_data: PullRequest) -> list[str]:
        """Get source refs including branch and commit hashes."""
        refs = []
        source_branch = pr_data.get_source_branch()
        if source_branch:
            refs.append(source_branch)

        source_commit_id = pr_data.get_source_commit_id()
        if source_commit_id:
            refs.append(source_commit_id)

        merge_commit_id = pr_data.get_merge_commit_id()
        if merge_commit_id:
            refs.append(merge_commit_id)

        return refs

    def _get_target_refs(self, pr_data: PullRequest) -> list[str]:
        """Get target refs including branch and commit hashes."""
        refs = []
        target_branch = pr_data.get_target_branch()
        if target_branch:
            refs.append(target_branch)

        target_commit_id = pr_data.get_target_commit_id()
        if target_commit_id:
            refs.append(target_commit_id)

        return refs

    async def _fetch_pull_request(self, pull_request_id: str) -> PullRequest:
        """Fetch pull request from GitHub API."""
        api_url = self.config.get_api_url()
        owner = self.config.get_owner()
        repo = self.config.get_repo()
        token = self.config.get_token()

        pr_url = f"{api_url}/repos/{owner}/{repo}/pulls/{pull_request_id}"
        commits_url = f"{api_url}/repos/{owner}/{repo}/pulls/{pull_request_id}/commits"

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        async with httpx.AsyncClient() as client:
            # Make both requests concurrently
            response_pr_task = client.get(pr_url, headers=headers)
            response_commits_task = client.get(commits_url, headers=headers)

            response_pr, response_commits = (
                await response_pr_task,
                await response_commits_task,
            )

            response_pr.raise_for_status()
            response_commits.raise_for_status()

            pr = response_pr.json()
            commits = response_commits.json()

        return PullRequest(pr, commits)

    async def download_image_as_base64(self, image_url: str) -> str | None:
        """Download an image from the given URL and return it as a data URI with URL-encoded base64 content"""
        token = self.config.get_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(image_url, headers=headers)

            if response.status_code == 200:
                # Encode the image content as base64
                encoded_image = base64.b64encode(response.content).decode("utf-8")

                # Always URL encode
                encoded_image = urllib.parse.quote(encoded_image)

                # Determine image type from URL (assuming it ends with extension)
                image_type = "png"  # Default
                if "." in image_url.split("/")[-1]:
                    ext = image_url.split("/")[-1].split(".")[-1].lower()
                    if ext in ["jpg", "jpeg", "png", "gif", "webp", "svg"]:
                        image_type = "jpeg" if ext in ["jpg", "jpeg"] else ext

                # Return as data URI
                return f"data:image/{image_type};base64,{encoded_image}"
            else:
                response.raise_for_status()
                return None


class GitHubIssueProvider(IssueProvider):
    """GitHub implementation of IssueProvider."""

    def __init__(self, config: GitHubConfig):
        self.config = config

    @staticmethod
    def from_config(config_data: dict[str, Any]) -> Optional["GitHubIssueProvider"]:
        """Create provider from configuration data.

        Args:
            config_data: GitHub configuration dictionary

        Returns:
            Provider instance if config is valid, None otherwise
        """
        config = GitHubConfig.from_config_data(config_data)
        if not config.is_configured():
            return None
        return GitHubIssueProvider(config)

    async def load(self, issue_id: str) -> IssueModel:
        """Load issue by ID.

        Args:
            issue_id: Issue identifier

        Returns:
            IssueModel with id and context
        """
        if self.config.get_use_mocks():
            issue = mock_fetch_issue_with_comments(issue_id)
        else:
            issue = await self._fetch_issue_with_comments(issue_id)

        context = issue.get_composed_issue_info()

        return IssueModel(id=issue_id, context=context)

    async def _fetch_issue_with_comments(self, issue_id: str) -> Issue:
        """Fetch issue and its comments from GitHub API."""
        api_url = self.config.get_api_url()
        owner = self.config.get_owner()
        repo = self.config.get_repo()
        token = self.config.get_token()

        issue_url = f"{api_url}/repos/{owner}/{repo}/issues/{issue_id}"
        comments_url = f"{api_url}/repos/{owner}/{repo}/issues/{issue_id}/comments"

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        async with httpx.AsyncClient() as client:
            # Make both requests concurrently
            response_issue_task = client.get(issue_url, headers=headers)
            response_comments_task = client.get(comments_url, headers=headers)

            response_issue, response_comments = (
                await response_issue_task,
                await response_comments_task,
            )

            response_issue.raise_for_status()
            response_comments.raise_for_status()

            issue_data = response_issue.json()
            comments_data = response_comments.json()

        return Issue(issue_data, comments_data)
