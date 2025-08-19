import json
from pathlib import Path
from unittest.mock import patch

from core.log import get_logger
from integrations.devops.models import PullRequest, WorkItem

logger = get_logger(logger_name="MockDevOps", level="INFO")


def get_mock_data(filename):
    """Load mock data from a JSON file"""
    try:
        mock_path = Path(__file__).parent / "mocks" / filename
        with open(mock_path, "r") as file:
            return json.load(file)
    except Exception as e:
        logger.error(f"Error loading mock data from {filename}: {str(e)}")
        return {}


def mock_get_pull_request_ids(self):
    # No pull requests to avoid multiple related-item prompts
    return []


def mock_fetch_work_item(work_item_id):
    """Mock implementation of fetch_work_item"""

    logger.info(f"Using mock data for work item {work_item_id}")

    if work_item_id == 111:
        raise ValueError("Mock: Work item 111 not found.")
    mock_data = get_mock_data("devops_workitem.json")
    work_item = WorkItem(mock_data)

    return work_item


def mock_fetch_pull_request(pull_request_id):
    """Mock implementation of fetch_pull_request"""

    logger.info(f"Using mock data for pull request {pull_request_id}")
    pr_data = get_mock_data("devops_pr.json")
    # commit_data = get_mock_data("devops_pr_commits.json")
    pr = PullRequest(pr_data, {})

    return pr
