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

from .models import Issue, MergeRequest


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
