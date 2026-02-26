from pathlib import Path
from typing import Any, cast
import json

from .models import Issue, MergeRequest, Pipeline


def _load_mock_file(file_path: str) -> dict[str, Any] | list[Any] | None:
    """Helper function to load mock data from a JSON file.

    Args:
        file_path: Path to the mock JSON file

    Returns:
        Loaded JSON data as dictionary, list, or None if error
    """
    try:
        # Get the directory of this file
        current_dir = Path(__file__).resolve().parent
        full_path = current_dir / file_path

        with full_path.open(encoding="utf-8") as file:
            return cast("dict[str, Any] | list[Any]", json.load(file))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading mock file {file_path}: {e}")
        return None


def mock_fetch_merge_request(merge_request_id: str) -> MergeRequest:
    """Fetch mock merge request data.

    Args:
        merge_request_id: Merge request ID to fetch

    Returns:
        MergeRequest object with mock data
    """
    # Load mock data from JSON files
    mr_data = _load_mock_file("mocks/gitlab_mr.json")
    commits_data = _load_mock_file("mocks/gitlab_commits.json")

    # Update the ID to match the requested ID
    if mr_data and isinstance(mr_data, dict):
        mr_data["iid"] = int(merge_request_id)

    # commits_data is always a list when loaded from gitlab_commits.json
    commits_list = commits_data if isinstance(commits_data, list) else []

    # Ensure mr_data is a dict for MergeRequest constructor
    mr_dict = mr_data if isinstance(mr_data, dict) else {}
    return MergeRequest(mr_dict, commits_list)


def mock_fetch_issue(issue_id: str) -> Issue:
    """Fetch mock issue data.

    Args:
        issue_id: Issue ID to fetch

    Returns:
        Issue object with mock data
    """
    # Load mock data from JSON file
    issue_data = _load_mock_file("mocks/gitlab_issue.json")

    # Update the ID to match the requested ID
    if issue_data and isinstance(issue_data, dict):
        issue_data["iid"] = int(issue_id)

    # Ensure issue_data is a dict for Issue constructor
    issue_dict = issue_data if isinstance(issue_data, dict) else {}
    return Issue(issue_dict)


def mock_fetch_pipeline(pipeline_id: str) -> Pipeline:
    """Fetch mock pipeline data.

    Args:
        pipeline_id: Pipeline ID to fetch

    Returns:
        Pipeline object with mock data
    """
    # Load mock data from JSON file
    mock_data = _load_mock_file("mocks/gitlab_pipeline.json")

    if not mock_data or not isinstance(mock_data, dict):
        # Return empty pipeline if file not found
        return Pipeline({}, [])

    pipeline_data = mock_data.get("pipeline", {})
    jobs_data = mock_data.get("jobs", [])

    # Update the ID to match the requested ID
    if isinstance(pipeline_data, dict):
        pipeline_data["id"] = int(pipeline_id)
        pipeline_data["iid"] = int(pipeline_id)

    return Pipeline(pipeline_data, cast("list[dict[str, Any]]", jobs_data))


def mock_list_pipelines(
    ref: str | None = None,
    status: str | None = None,
    count: int = 20,
) -> list[dict[str, Any]]:
    """Fetch mock pipeline list data with optional filtering.

    Args:
        ref: Optional git reference to filter by
        status: Optional pipeline status to filter by
        count: Maximum number of results to return

    Returns:
        List of pipeline data dictionaries
    """
    mock_data = _load_mock_file("mocks/gitlab_pipelines_list.json")

    if not mock_data or not isinstance(mock_data, list):
        return []

    results = cast("list[dict[str, Any]]", mock_data)
    if ref:
        results = [p for p in results if p.get("ref") == ref]
    if status:
        results = [p for p in results if p.get("status") == status]

    return results[:count]


def mock_fetch_pipeline_job_log(pipeline_id: str, job_id: str) -> str:
    """Fetch mock job log data.

    Args:
        pipeline_id: Pipeline ID (unused for mock)
        job_id: Job ID to fetch logs for

    Returns:
        Job log as string
    """
    # Suppress unused argument warning
    _ = pipeline_id

    # Load mock data from JSON file
    mock_data = _load_mock_file("mocks/gitlab_pipeline.json")

    if not mock_data or not isinstance(mock_data, dict):
        return "No log data available"

    job_logs = mock_data.get("job_logs", {})
    return cast("str", job_logs.get(job_id, "No log available for this job"))
