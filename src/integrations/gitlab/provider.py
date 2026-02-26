from typing import Any, Optional, cast
import base64
import builtins
import urllib.parse

import httpx

from core.log import get_logger
from core.protocols.provider_protocols import (
    IssueModel,
    IssueProvider,
    PipelineListFilter,
    PipelineModel,
    PipelineProvider,
    PipelineSummaryModel,
    PullRequestModel,
    PullRequestProvider,
)

from .config import GitLabConfig
from .mock_gitlab import (
    mock_fetch_issue,
    mock_fetch_merge_request,
    mock_fetch_pipeline,
    mock_fetch_pipeline_job_log,
    mock_list_pipelines,
)
from .models import Issue, MergeRequest, Pipeline

logger = get_logger(__name__)


class GitLabMergeRequestProvider(PullRequestProvider):
    """GitLab implementation of PullRequestProvider."""

    def __init__(self, config: GitLabConfig):
        self.config = config

    @staticmethod
    def from_config(
        config_data: dict[str, Any],
    ) -> Optional["GitLabMergeRequestProvider"]:
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
            target_refs=target_refs,
        )

    def _get_source_refs(self, mr_data: MergeRequest) -> list[str]:
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

    def _get_target_refs(self, mr_data: MergeRequest) -> list[str]:
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
        commits_url = (
            f"{api_url}/projects/{project_id}/merge_requests/{merge_request_id}/commits"
        )

        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

        async with httpx.AsyncClient() as client:
            # Make both requests concurrently
            response_mr_task = client.get(mr_url, headers=headers)
            response_commits_task = client.get(commits_url, headers=headers)

            response_mr, response_commits = (
                await response_mr_task,
                await response_commits_task,
            )

            response_mr.raise_for_status()
            response_commits.raise_for_status()

            mr = response_mr.json()
            commits = response_commits.json()

        return MergeRequest(mr, commits)

    async def download_image_as_base64(self, image_url: str) -> str | None:
        """Download an image from the given URL and return it as a data URI with URL-encoded base64 content"""
        token = self.config.get_token()

        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

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
    def from_config(config_data: dict[str, Any]) -> Optional["GitLabIssueProvider"]:
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

        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return Issue(response.json())


class GitLabPipelineProvider(PipelineProvider):
    """GitLab implementation of PipelineProvider."""

    def __init__(self, config: GitLabConfig):
        self.config = config

        # Log warning if mocks are enabled
        if self.config.get_use_mocks():
            logger.warning(
                "GITLAB MOCK MODE IS ENABLED! "
                "You will receive FAKE data from local JSON files instead of real "
                "GitLab API data. "
                "To use REAL data: Set GITLAB_MOCK=false in your .env file or "
                "remove the variable entirely."
            )

    @staticmethod
    def from_config(config_data: dict[str, Any]) -> Optional["GitLabPipelineProvider"]:
        """Create provider from configuration data.

        Args:
            config_data: GitLab configuration dictionary

        Returns:
            Provider instance if config is valid, None otherwise
        """
        config = GitLabConfig(config_data)
        if not config.is_configured() and not config.get_use_mocks():
            return None
        return GitLabPipelineProvider(config)

    async def load(self, pipeline_id: str) -> PipelineModel:
        """Load pipeline by ID.

        Args:
            pipeline_id: Pipeline identifier

        Returns:
            PipelineModel with pipeline data and context
        """
        if self.config.get_use_mocks():
            pipeline = mock_fetch_pipeline(pipeline_id)
        else:
            pipeline = await self._fetch_pipeline(pipeline_id)

        return PipelineModel(
            id=pipeline_id,
            context=pipeline.get_composed_pipeline_info(),
            status=pipeline.get_status(),
            ref=pipeline.get_ref(),
            web_url=pipeline.get_web_url(),
            jobs=pipeline.get_jobs(),
            failed_jobs=pipeline.get_failed_jobs(),
            duration=pipeline.get_duration(),
            coverage=pipeline.get_coverage(),
        )

    async def list(
        self, filters: PipelineListFilter | None = None
    ) -> builtins.list[PipelineSummaryModel]:
        """List pipelines with optional filtering.

        Args:
            filters: Optional filter criteria for ref, status, and result count

        Returns:
            List of PipelineSummaryModel with pipeline summaries
        """
        resolved_filters = filters or PipelineListFilter()

        if self.config.get_use_mocks():
            pipelines_data = mock_list_pipelines(
                ref=resolved_filters.ref,
                status=resolved_filters.status,
                count=resolved_filters.count,
            )
        else:
            pipelines_data = await self._fetch_pipelines_list(resolved_filters)

        return [
            PipelineSummaryModel(
                id=str(p.get("id", "")),
                status=p.get("status", ""),
                ref=p.get("ref", ""),
                sha=p.get("sha", ""),
                web_url=p.get("web_url", ""),
                created_at=p.get("created_at", ""),
                updated_at=p.get("updated_at", ""),
                source=p.get("source", ""),
            )
            for p in pipelines_data
        ]

    async def _fetch_pipelines_list(
        self, filters: PipelineListFilter
    ) -> builtins.list[dict[str, Any]]:
        """Fetch pipeline list from GitLab API.

        Args:
            filters: Filter criteria for the API request

        Returns:
            List of pipeline data dictionaries
        """
        api_url = self.config.get_api_url()
        project_id = self.config.get_project_id()
        token = self.config.get_token()

        url = f"{api_url}/projects/{project_id}/pipelines"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

        params: dict[str, str | int] = {
            "per_page": min(filters.count, 100),
            "order_by": "id",
            "sort": "desc",
        }
        if filters.ref:
            params["ref"] = filters.ref
        if filters.status:
            params["status"] = filters.status

        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return cast("list[dict[str, Any]]", response.json())

    async def _fetch_pipeline(self, pipeline_id: str) -> Pipeline:
        """Fetch pipeline from GitLab API."""
        api_url = self.config.get_api_url()
        project_id = self.config.get_project_id()
        token = self.config.get_token()

        pipeline_url = f"{api_url}/projects/{project_id}/pipelines/{pipeline_id}"
        jobs_url = f"{api_url}/projects/{project_id}/pipelines/{pipeline_id}/jobs"

        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

        async with httpx.AsyncClient() as client:
            # Fetch pipeline and jobs concurrently
            response_pipeline_task = client.get(pipeline_url, headers=headers)
            response_jobs_task = client.get(jobs_url, headers=headers)

            response_pipeline, response_jobs = (
                await response_pipeline_task,
                await response_jobs_task,
            )

            response_pipeline.raise_for_status()
            response_jobs.raise_for_status()

            pipeline_data = response_pipeline.json()
            jobs_data = response_jobs.json()

        return Pipeline(pipeline_data, jobs_data)

    async def get_job_log(self, pipeline_id: str, job_id: str) -> str:
        """Get log for a specific job.

        Args:
            pipeline_id: Pipeline identifier
            job_id: Job identifier

        Returns:
            Job log as string
        """
        if self.config.get_use_mocks():
            return mock_fetch_pipeline_job_log(pipeline_id, job_id)

        api_url = self.config.get_api_url()
        project_id = self.config.get_project_id()
        token = self.config.get_token()

        log_url = f"{api_url}/projects/{project_id}/jobs/{job_id}/trace"
        headers = {"Authorization": f"Bearer {token}", "Accept": "text/plain"}

        async with httpx.AsyncClient() as client:
            response = await client.get(log_url, headers=headers)
            response.raise_for_status()
            return response.text
