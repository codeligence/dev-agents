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

from .models import JiraIssue


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


def mock_fetch_issue(issue_id: str) -> JiraIssue:
    """Fetch mock Jira issue data.

    Args:
        issue_id: Issue ID to fetch (e.g., 'PROJ-123')

    Returns:
        JiraIssue object with mock data
    """
    # Load mock data from JSON file
    issue_data = _load_mock_file("mocks/jira_issue.json")

    # Update the key to match the requested ID
    if issue_data and isinstance(issue_data, dict):
        issue_data["key"] = issue_id
        # Also update the id field if present
        if "id" in issue_data:
            issue_data["id"] = str(
                hash(issue_id) % 100000
            )  # Generate consistent fake ID

    # Ensure issue_data is a dict for JiraIssue constructor
    issue_dict = issue_data if isinstance(issue_data, dict) else {}
    return JiraIssue(issue_dict)
