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


import base64
import urllib.parse
from typing import Optional, Dict, Any, List
import httpx
from core.protocols.provider_protocols import PullRequestModel, IssueModel, PullRequestProvider, IssueProvider
from .config import GitLabConfig
from .models import MergeRequest, Issue
from .mock_gitlab import mock_fetch_merge_request, mock_fetch_issue


class GitLabMergeRequestProvider(PullRequestProvider):
    """GitLab implementation of PullRequestProvider."""

    def __init__(self, config: GitLabConfig):
        self.config = config

    @staticmethod
    def from_config(config_data: Dict[str, Any]) -> Optional['GitLabMergeRequestProvider']:
        """Create provider from configuration data.

        Args:
            config_data: GitLab configuration dictionary

        Returns:
            Provider instance if config is valid, None otherwise
        """
        config = GitLabConfig(config_data)
        if not config.is_configured():
            return None
        return GitLabMergeRequestProvider(config)

    async def load(self, merge_request_id: str) -> PullRequestModel:
        """Load merge request by ID.

        Args:
            merge_request_id: Merge request identifier

        Returns:
            PullRequestModel with id and context
        """
        if self.config.get_use_mocks():
            mr_data = mock_fetch_merge_request(merge_request_id)
            context = mr_data.get_composed_MR_info()
            source_branch = mr_data.get_source_branch()
            target_branch = mr_data.get_target_branch()
            source_refs = self._get_source_refs(mr_data)
            target_refs = self._get_target_refs(mr_data)
        else:
            mr_data = await self._fetch_merge_request(merge_request_id)
            context = mr_data.get_composed_MR_info()
            source_branch = mr_data.get_source_branch()
            target_branch = mr_data.get_target_branch()
            source_refs = self._get_source_refs(mr_data)
            target_refs = self._get_target_refs(mr_data)

        return PullRequestModel(
            id=merge_request_id,
            context=context,
            source_branch=source_branch,
            target_branch=target_branch,
            source_refs=source_refs,
            target_refs=target_refs
        )

    def _get_source_refs(self, mr_data: MergeRequest) -> List[str]:
        """Get source refs including branch and commit hashes."""
        refs = []
        source_branch = mr_data.get_source_branch()
        if source_branch:
            refs.append(source_branch)

        source_commit_id = mr_data.get_source_commit_id()
        if source_commit_id:
            refs.append(source_commit_id)

        merge_commit_id = mr_data.get_merge_commit_id()
        if merge_commit_id:
            refs.append(merge_commit_id)

        return refs

    def _get_target_refs(self, mr_data: MergeRequest) -> List[str]:
        """Get target refs including branch and commit hashes."""
        refs = []
        target_branch = mr_data.get_target_branch()
        if target_branch:
            refs.append(target_branch)

        target_commit_id = mr_data.get_target_commit_id()
        if target_commit_id:
            refs.append(target_commit_id)

        return refs

    async def _fetch_merge_request(self, merge_request_id: str) -> MergeRequest:
        """Fetch merge request from GitLab API."""
        api_url = self.config.get_api_url()
        project_id = self.config.get_project_id()
        token = self.config.get_token()

        mr_url = f"{api_url}/projects/{project_id}/merge_requests/{merge_request_id}"
        commits_url = f"{api_url}/projects/{project_id}/merge_requests/{merge_request_id}/commits"

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }

        async with httpx.AsyncClient() as client:
            # Make both requests concurrently
            response_mr_task = client.get(mr_url, headers=headers)
            response_commits_task = client.get(commits_url, headers=headers)

            response_mr, response_commits = await response_mr_task, await response_commits_task

            response_mr.raise_for_status()
            response_commits.raise_for_status()

            mr = response_mr.json()
            commits = response_commits.json()

        return MergeRequest(mr, commits)

    async def download_image_as_base64(self, image_url: str) -> Optional[str]:
        """Download an image from the given URL and return it as a data URI with URL-encoded base64 content"""
        token = self.config.get_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
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


class GitLabIssueProvider(IssueProvider):
    """GitLab implementation of IssueProvider."""

    def __init__(self, config: GitLabConfig):
        self.config = config

    @staticmethod
    def from_config(config_data: Dict[str, Any]) -> Optional['GitLabIssueProvider']:
        """Create provider from configuration data.

        Args:
            config_data: GitLab configuration dictionary

        Returns:
            Provider instance if config is valid, None otherwise
        """
        config = GitLabConfig(config_data)
        if not config.is_configured() and not config.get_use_mocks():
            return None
        return GitLabIssueProvider(config)

    async def load(self, issue_id: str) -> IssueModel:
        """Load issue by ID.

        Args:
            issue_id: Issue identifier

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

    async def _fetch_issue(self, issue_id: str) -> Issue:
        """Fetch issue from GitLab API."""
        api_url = self.config.get_api_url()
        project_id = self.config.get_project_id()
        token = self.config.get_token()

        url = f"{api_url}/projects/{project_id}/issues/{issue_id}"

        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return Issue(response.json())
