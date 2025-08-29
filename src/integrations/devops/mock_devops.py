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
from typing import Any
import json

from core.log import get_logger
from integrations.devops.models import PullRequest, WorkItem

logger = get_logger(logger_name="MockDevOps", level="INFO")


def get_mock_data(filename: str) -> dict[str, Any]:
    """Load mock data from a JSON file"""
    try:
        mock_path = Path(__file__).parent / "mocks" / filename
        with mock_path.open() as file:
            data = json.load(file)
            return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.error(f"Error loading mock data from {filename}: {str(e)}")
        return {}


def mock_get_pull_request_ids(_self: Any) -> list[str]:
    # No pull requests to avoid multiple related-item prompts
    return []


def mock_fetch_work_item(work_item_id: int) -> WorkItem:
    """Mock implementation of fetch_work_item"""

    logger.info(f"Using mock data for work item {work_item_id}")

    if work_item_id == 111:
        raise ValueError("Mock: Work item 111 not found.")
    mock_data = get_mock_data("devops_workitem.json")
    work_item = WorkItem(mock_data)

    return work_item


def mock_fetch_pull_request(pull_request_id: int) -> PullRequest:
    """Mock implementation of fetch_pull_request"""

    logger.info(f"Using mock data for pull request {pull_request_id}")
    pr_data = get_mock_data("devops_pr.json")
    pr = PullRequest(pr_data, [])  # Empty list for commits

    return pr
