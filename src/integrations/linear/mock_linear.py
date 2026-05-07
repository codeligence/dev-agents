from pathlib import Path
from typing import Any, cast
import json

from .models import LinearIssue


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


def mock_fetch_issue(issue_id: str) -> LinearIssue:
    """Fetch mock Linear issue data.

    Args:
        issue_id: Issue identifier (e.g., 'ENG-123')

    Returns:
        LinearIssue object with mock data
    """
    # Load mock data from JSON file
    issue_data = _load_mock_file("mocks/linear_issue.json")

    # Update the identifier to match the requested ID
    if issue_data and isinstance(issue_data, dict):
        issue_data["identifier"] = issue_id

    # Ensure issue_data is a dict for LinearIssue constructor
    issue_dict = issue_data if isinstance(issue_data, dict) else {}
    return LinearIssue(issue_dict)
