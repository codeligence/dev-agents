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


from pathlib import Path
from typing import Any, cast
import json

from .models import Issue, PullRequest


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


def mock_fetch_pull_request(pull_request_id: str) -> PullRequest:
    """Create a mock pull request for testing purposes.

    Args:
        pull_request_id: ID of the pull request to mock

    Returns:
        Mock pull request object
    """
    # Load PR data from JSON file
    mock_pr_data = _load_mock_file("mocks/github_pr.json")

    # Override the PR number with the requested ID
    if mock_pr_data and isinstance(mock_pr_data, dict):
        mock_pr_data["number"] = int(pull_request_id)
    else:
        # Fallback if JSON file not found or invalid
        mock_pr_data = {
            "number": int(pull_request_id),
            "title": f"Mock pull request #{pull_request_id}",
            "state": "open",
            "created_at": "2025-08-12T08:00:00Z",
            "updated_at": "2025-08-12T09:00:00Z",
            "user": {"login": "mock-user", "name": "Mock User"},
            "head": {
                "ref": "feature/mock-feature",
                "sha": "abcdef1234567890abcdef1234567890abcdef12",
            },
            "base": {"ref": "main", "sha": "1234567890abcdef1234567890abcdef12345678"},
        }

    # Load commits data from JSON file
    mock_commits = _load_mock_file("mocks/github_commits.json")
    if not mock_commits or not isinstance(mock_commits, list):
        # Fallback if JSON file not found or invalid
        mock_commits = [
            {
                "sha": "abcdef1234567890abcdef1234567890abcdef12",
                "commit": {"message": "Mock commit message for testing"},
            }
        ]

    # Ensure mock_pr_data is a dict for PullRequest constructor
    pr_dict = mock_pr_data if isinstance(mock_pr_data, dict) else {}
    return PullRequest(pr_dict, mock_commits)


def mock_fetch_issue_with_comments(issue_id: str) -> Issue:
    """Create a mock issue for testing purposes.

    Args:
        issue_id: ID of the issue to mock

    Returns:
        Mock issue object with comments
    """
    # Load issue data from JSON file
    mock_issue_data = _load_mock_file("mocks/github_issue.json")

    # Override the issue number with the requested ID
    if mock_issue_data and isinstance(mock_issue_data, dict):
        mock_issue_data["number"] = int(issue_id)
    else:
        # Fallback if JSON file not found or invalid
        mock_issue_data = {
            "number": int(issue_id),
            "title": f"Mock issue #{issue_id}",
            "state": "open",
            "created_at": "2025-08-12T08:00:00Z",
            "updated_at": "2025-08-12T09:00:00Z",
            "user": {"login": "mock-user", "name": "Mock User"},
            "body": "This is a mock issue description for testing purposes.",
            "labels": [{"name": "bug"}, {"name": "documentation"}],
            "milestone": {"title": "Sprint 1"},
        }

    # Load comments data from JSON file
    mock_comments = _load_mock_file("mocks/github_issue_comments.json")
    if not mock_comments or not isinstance(mock_comments, list):
        # Fallback if JSON file not found or invalid
        mock_comments = [
            {
                "id": 1001,
                "body": f"This is a mock comment for issue #{issue_id}",
                "user": {"login": "mock-commenter", "name": "Mock Commenter"},
                "created_at": "2025-08-12T10:00:00Z",
                "updated_at": "2025-08-12T10:00:00Z",
            }
        ]

    # Ensure issue_data is a dict for Issue constructor
    issue_dict = mock_issue_data if isinstance(mock_issue_data, dict) else {}
    comments_list = mock_comments if isinstance(mock_comments, list) else []
    return Issue(issue_dict, comments_list)
