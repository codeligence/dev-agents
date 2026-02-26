from pathlib import Path
from typing import Any, cast
import json

from .models import PullRequest


def _load_mock_file(file_path: str) -> dict[str, Any] | list[Any] | None:
    """Helper function to load mock data from a JSON file.

    Args:
        file_path: Path to the mock JSON file

    Returns:
        Loaded JSON data as dictionary, list, or None if error
    """
    try:
        current_dir = Path(__file__).resolve().parent
        full_path = current_dir / file_path

        with full_path.open(encoding="utf-8") as file:
            return cast("dict[str, Any] | list[Any]", json.load(file))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading mock file {file_path}: {e}")
        return None


def mock_fetch_pull_request(pull_request_id: str) -> PullRequest:
    """Fetch mock pull request data.

    Args:
        pull_request_id: Pull request ID to fetch

    Returns:
        PullRequest object with mock data
    """
    pr_data = _load_mock_file("mocks/bitbucket_pr.json")
    commits_data = _load_mock_file("mocks/bitbucket_commits.json")

    # Update the ID to match the requested ID
    if pr_data and isinstance(pr_data, dict):
        pr_data["id"] = int(pull_request_id)

    # BitBucket commits are wrapped in a 'values' array
    commits_list: list[dict[str, Any]] = []
    if commits_data and isinstance(commits_data, dict):
        commits_list = commits_data.get("values", [])

    pr_dict = pr_data if isinstance(pr_data, dict) else {}
    return PullRequest(pr_dict, commits_list)
