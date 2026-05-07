from typing import Any, Optional
import re

import httpx

from core.log import get_logger
from core.protocols.provider_protocols import IssueModel, IssueProvider

from .config import LinearConfig
from .mock_linear import mock_fetch_issue
from .models import LinearIssue

logger = get_logger(__name__)

# GraphQL query for fetching a single issue with all relevant fields
ISSUE_QUERY = """
query IssueByIdentifier($id: String!) {
  issue(id: $id) {
    id
    identifier
    title
    description
    url
    priority
    estimate
    dueDate
    createdAt
    updatedAt
    completedAt
    canceledAt
    state {
      id
      name
      type
    }
    assignee {
      id
      name
      email
    }
    creator {
      id
      name
      email
    }
    team {
      id
      name
      key
    }
    project {
      id
      name
    }
    cycle {
      id
      name
    }
    labels {
      nodes {
        id
        name
        color
      }
    }
    parent {
      id
      identifier
    }
    children {
      nodes {
        id
        identifier
      }
    }
    comments {
      nodes {
        id
        body
        createdAt
        user {
          id
          name
          email
        }
      }
    }
  }
}
"""

LINEAR_API_URL = "https://api.linear.app/graphql"


class LinearIssueProvider(IssueProvider):
    """Linear implementation of IssueProvider."""

    def __init__(self, config: LinearConfig):
        self.config = config

    @staticmethod
    def from_config(config_data: dict[str, Any]) -> Optional["LinearIssueProvider"]:
        """Create provider from configuration data.

        Args:
            config_data: Linear configuration dictionary

        Returns:
            Provider instance if config is valid, None otherwise
        """
        config = LinearConfig(config_data)
        if not config.is_configured():
            return None
        return LinearIssueProvider(config)

    async def load(self, issue_id: str) -> IssueModel:
        """Load issue by identifier (e.g., 'ENG-123').

        Args:
            issue_id: Issue identifier (human-readable like 'ENG-123')

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

    def extract_issue_ids(self, text: str) -> list[str]:
        """Extract Linear issue IDs from text.

        Matches patterns like ENG-123, TEAM-456, etc.

        Args:
            text: Text to search for Linear issue identifiers

        Returns:
            List of Linear issue IDs found in text, normalized to uppercase
        """
        # Linear identifiers follow the pattern: TEAM_KEY-NUMBER
        # Team keys are typically 2-10 uppercase letters
        pattern = r"\b([A-Z]{2,10}-\d{1,6})\b"
        matches = re.findall(pattern, text, re.IGNORECASE)

        # Normalize to uppercase and deduplicate
        normalized_ids = set()
        for match in matches:
            normalized_ids.add(match.upper())

        return list(normalized_ids)

    async def _fetch_issue(self, issue_id: str) -> LinearIssue:
        """Fetch issue from Linear GraphQL API.

        Args:
            issue_id: Issue identifier (e.g., 'ENG-123')

        Returns:
            LinearIssue instance with API data
        """
        api_key = self.config.get_api_key()

        headers = {
            "Authorization": str(api_key),
            "Content-Type": "application/json",
        }

        payload = {
            "query": ISSUE_QUERY,
            "variables": {"id": issue_id},
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                LINEAR_API_URL,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            result = response.json()

            if "errors" in result:
                error_messages = [e.get("message", "") for e in result["errors"]]
                raise RuntimeError(f"Linear API errors: {'; '.join(error_messages)}")

            issue_data = result.get("data", {}).get("issue")
            if issue_data is None:
                raise RuntimeError(f"Issue '{issue_id}' not found in Linear")

            return LinearIssue(issue_data)
