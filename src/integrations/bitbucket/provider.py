from typing import Any, Optional
import base64
import urllib.parse

import httpx

from core.protocols.provider_protocols import (
    PullRequestModel,
    PullRequestProvider,
)

from .config import BitBucketConfig
from .mock_bitbucket import mock_fetch_pull_request
from .models import PullRequest


class BitBucketPullRequestProvider(PullRequestProvider):
    """BitBucket implementation of PullRequestProvider."""

    def __init__(self, config: BitBucketConfig):
        self.config = config

    @staticmethod
    def from_config(
        config_data: dict[str, Any],
    ) -> Optional["BitBucketPullRequestProvider"]:
        """Create provider from configuration data.

        Args:
            config_data: BitBucket configuration dictionary

        Returns:
            Provider instance if config is valid, None otherwise
        """
        config = BitBucketConfig(config_data)
        if not config.is_configured():
            return None
        return BitBucketPullRequestProvider(config)

    async def load(self, pull_request_id: str) -> PullRequestModel:
        """Load pull request by ID.

        Args:
            pull_request_id: Pull request identifier

        Returns:
            PullRequestModel with id and context
        """
        if self.config.get_use_mocks():
            pr_data = mock_fetch_pull_request(pull_request_id)
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
        """Fetch pull request from BitBucket API."""
        api_url = self.config.get_api_url()
        workspace = self.config.get_workspace()
        repo_slug = self.config.get_repo_slug()
        username = self.config.get_username()
        token = self.config.get_token()

        pr_url = (
            f"{api_url}/repositories/{workspace}/{repo_slug}"
            f"/pullrequests/{pull_request_id}"
        )
        commits_url = (
            f"{api_url}/repositories/{workspace}/{repo_slug}"
            f"/pullrequests/{pull_request_id}/commits"
        )

        headers = {"Accept": "application/json"}
        # BitBucket uses Basic Auth with username (email) and API token
        auth = httpx.BasicAuth(username or "", token or "")

        async with httpx.AsyncClient() as client:
            # Make both requests concurrently
            response_pr_task = client.get(pr_url, headers=headers, auth=auth)
            response_commits_task = client.get(commits_url, headers=headers, auth=auth)

            response_pr, response_commits = (
                await response_pr_task,
                await response_commits_task,
            )

            response_pr.raise_for_status()
            response_commits.raise_for_status()

            pr = response_pr.json()
            commits_response = response_commits.json()
            # BitBucket returns commits in a 'values' array
            commits = commits_response.get("values", [])

        return PullRequest(pr, commits)

    async def download_image_as_base64(self, image_url: str) -> str | None:
        """Download an image from the given URL and return it as a data URI."""
        username = self.config.get_username()
        token = self.config.get_token()

        headers = {"Accept": "application/json"}
        auth = httpx.BasicAuth(username or "", token or "")

        async with httpx.AsyncClient() as client:
            response = await client.get(image_url, headers=headers, auth=auth)

            if response.status_code == 200:
                encoded_image = base64.b64encode(response.content).decode("utf-8")
                encoded_image = urllib.parse.quote(encoded_image)

                image_type = "png"
                if "." in image_url.split("/")[-1]:
                    ext = image_url.split("/")[-1].split(".")[-1].lower()
                    if ext in ["jpg", "jpeg", "png", "gif", "webp", "svg"]:
                        image_type = "jpeg" if ext in ["jpg", "jpeg"] else ext

                return f"data:image/{image_type};base64,{encoded_image}"
            else:
                response.raise_for_status()
                return None
