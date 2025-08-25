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
from core.protocols.provider_protocols import PullRequestModel, IssueModel, IssueProvider, PullRequestProvider
from .config import AzureDevOpsConfig
from .models import PullRequest, WorkItem
from .mock_devops import mock_fetch_work_item, mock_fetch_pull_request


class AzureDevOpsPullRequestProvider(PullRequestProvider):
    """Azure DevOps implementation of PullRequestProvider."""

    def __init__(self, config: AzureDevOpsConfig):
        self.config = config

    @staticmethod
    def from_config(config_data: Dict[str, Any]) -> Optional['AzureDevOpsPullRequestProvider']:
        """Create provider from configuration data.

        Args:
            config_data: Azure DevOps configuration dictionary

        Returns:
            Provider instance if config is valid, None otherwise
        """
        config = AzureDevOpsConfig(config_data)
        if not config.is_configured():
            return None
        return AzureDevOpsPullRequestProvider(config)

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
            target_refs=target_refs
        )

    def _get_source_refs(self, pr_data: PullRequest) -> List[str]:
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

    def _get_target_refs(self, pr_data: PullRequest) -> List[str]:
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
        """Fetch pull request from Azure DevOps API."""
        base_url = self.config.get_url()
        organization = self.config.get_organization()
        project = self.config.get_project()
        repo_id = self.config.get_repo_id()
        pat = self.config.get_pat()

        pr_url = f"{base_url}/{organization}/{project}/_apis/git/repositories/{repo_id}/pullRequests/{pull_request_id}?api-version=7.1"
        commits_url = f"{base_url}/{organization}/{project}/_apis/git/repositories/{repo_id}/pullRequests/{pull_request_id}/commits?api-version=7.1"

        async with httpx.AsyncClient(auth=("", pat)) as client:
            # Make both requests concurrently
            response_pr_task = client.get(pr_url)
            response_commits_task = client.get(commits_url)

            response_pr, response_commits = await response_pr_task, await response_commits_task

            response_pr.raise_for_status()
            response_commits.raise_for_status()

            pr = response_pr.json()
            commits = response_commits.json()

        return PullRequest(pr, commits)

    async def download_image_as_base64(self, image_url: str) -> Optional[str]:
        """Download an image from the given URL and return it as a data URI with URL-encoded base64 content"""
        pat = self.config.get_pat()

        async with httpx.AsyncClient(auth=("", pat)) as client:
            response = await client.get(image_url)

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


class AzureDevOpsIssueProvider(IssueProvider):
    """Azure DevOps implementation of IssueProvider."""

    def __init__(self, config: AzureDevOpsConfig):
        self.config = config

    @staticmethod
    def from_config(config_data: Dict[str, Any]) -> Optional['AzureDevOpsIssueProvider']:
        """Create provider from configuration data.

        Args:
            config_data: Azure DevOps configuration dictionary

        Returns:
            Provider instance if config is valid, None otherwise
        """
        config = AzureDevOpsConfig(config_data)
        if not config.is_configured():
            return None
        return AzureDevOpsIssueProvider(config)

    async def load(self, issue_id: str) -> IssueModel:
        """Load work item by ID.

        Args:
            issue_id: Work item identifier

        Returns:
            IssueModel with id and context
        """
        if self.config.get_use_mocks():
            work_item = mock_fetch_work_item(issue_id)
            context = work_item.get_composed_work_item_info()
        else:
            work_item = await self._fetch_work_item(issue_id)
            context = work_item.get_composed_work_item_info()

        return IssueModel(id=issue_id, context=context)

    async def _fetch_work_item(self, work_item_id: str) -> WorkItem:
        """Fetch work item from Azure DevOps API."""
        base_url = self.config.get_url()
        organization = self.config.get_organization()
        project = self.config.get_project()
        pat = self.config.get_pat()

        url = f"{base_url}/{organization}/{project}/_apis/wit/workitems/{work_item_id}?$expand=Relations&api-version=7.1-preview.3"

        async with httpx.AsyncClient(auth=("", pat)) as client:
            response = await client.get(url)
            response.raise_for_status()
            return WorkItem(response.json())
