from pathlib import Path
import json

from integrations.linear.models import (
    PRIORITY_LABELS,
    LinearComment,
    LinearIssue,
    LinearLabel,
    LinearUser,
)


def _load_mock_issue() -> dict:
    """Load the mock issue JSON for testing."""
    mock_path = (
        Path(__file__).resolve().parent.parent.parent.parent
        / "src"
        / "integrations"
        / "linear"
        / "mocks"
        / "linear_issue.json"
    )
    with mock_path.open(encoding="utf-8") as f:
        return json.load(f)


class TestLinearUser:
    """Test cases for LinearUser."""

    def test_user_with_data(self):
        """Test LinearUser with valid data."""
        user = LinearUser(
            {"id": "user-001", "name": "Test User", "email": "test@example.com"}
        )
        assert user.get_id() == "user-001"
        assert user.get_name() == "Test User"
        assert user.get_email() == "test@example.com"

    def test_user_with_none(self):
        """Test LinearUser with None data."""
        user = LinearUser(None)
        assert user.get_id() == ""
        assert user.get_name() == ""
        assert user.get_email() == ""

    def test_user_with_empty_dict(self):
        """Test LinearUser with empty dictionary."""
        user = LinearUser({})
        assert user.get_id() == ""
        assert user.get_name() == ""
        assert user.get_email() == ""


class TestLinearLabel:
    """Test cases for LinearLabel."""

    def test_label_with_data(self):
        """Test LinearLabel with valid data."""
        label = LinearLabel({"id": "label-001", "name": "bug", "color": "#FF0000"})
        assert label.get_name() == "bug"
        assert label.get_color() == "#FF0000"

    def test_label_with_empty_data(self):
        """Test LinearLabel with empty data."""
        label = LinearLabel({})
        assert label.get_name() == ""
        assert label.get_color() == ""


class TestLinearComment:
    """Test cases for LinearComment."""

    def test_comment_with_data(self):
        """Test LinearComment with valid data."""
        comment = LinearComment(
            {
                "id": "comment-001",
                "body": "This is a comment.",
                "createdAt": "2026-03-21T09:00:00.000Z",
                "user": {
                    "id": "user-001",
                    "name": "Test User",
                    "email": "test@example.com",
                },
            }
        )
        assert comment.get_body() == "This is a comment."
        assert comment.get_created_at() == "2026-03-21T09:00:00.000Z"
        assert comment.get_user().get_name() == "Test User"

    def test_comment_with_no_user(self):
        """Test LinearComment with missing user."""
        comment = LinearComment({"body": "Orphan comment"})
        assert comment.get_user().get_name() == ""


class TestLinearIssue:
    """Test cases for LinearIssue."""

    def test_issue_from_mock_data(self):
        """Test LinearIssue with mock data."""
        data = _load_mock_issue()
        issue = LinearIssue(data)

        assert issue.get_id() == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        assert issue.get_identifier() == "ENG-123"
        assert issue.get_title() == "Implement Linear integration for dev-agents"
        assert "Linear integration" in issue.get_description()
        assert issue.get_state() == "In Progress"
        assert issue.get_state_type() == "started"
        assert issue.get_priority() == 2
        assert issue.get_priority_label() == "High"
        assert issue.get_team_name() == "Engineering"
        assert issue.get_team_key() == "ENG"
        assert issue.get_project_name() == "Platform Integrations"
        assert issue.get_cycle_name() == "Sprint 12"
        assert issue.get_estimate() == 3
        assert issue.get_due_date() == "2026-04-15"
        assert issue.get_url() == "https://linear.app/example-team/issue/ENG-123"

    def test_issue_assignee(self):
        """Test issue assignee."""
        data = _load_mock_issue()
        issue = LinearIssue(data)
        assignee = issue.get_assignee()

        assert assignee.get_name() == "Test Developer"
        assert assignee.get_email() == "developer@example.com"

    def test_issue_creator(self):
        """Test issue creator."""
        data = _load_mock_issue()
        issue = LinearIssue(data)
        creator = issue.get_creator()

        assert creator.get_name() == "Project Manager"
        assert creator.get_email() == "pm@example.com"

    def test_issue_labels(self):
        """Test issue labels."""
        data = _load_mock_issue()
        issue = LinearIssue(data)
        labels = issue.get_labels()

        assert len(labels) == 2
        label_names = [label.get_name() for label in labels]
        assert "enhancement" in label_names
        assert "integration" in label_names

    def test_issue_comments(self):
        """Test issue comments."""
        data = _load_mock_issue()
        issue = LinearIssue(data)
        comments = issue.get_comments()

        assert len(comments) == 2
        assert "GraphQL client" in comments[0].get_body()
        assert comments[0].get_user().get_name() == "Test Developer"

    def test_issue_no_parent(self):
        """Test issue with no parent."""
        data = _load_mock_issue()
        issue = LinearIssue(data)
        assert issue.get_parent_identifier() is None

    def test_issue_no_children(self):
        """Test issue with no children."""
        data = _load_mock_issue()
        issue = LinearIssue(data)
        assert issue.get_children_identifiers() == []

    def test_issue_with_parent(self):
        """Test issue with parent."""
        data = {"parent": {"id": "parent-001", "identifier": "ENG-100"}}
        issue = LinearIssue(data)
        assert issue.get_parent_identifier() == "ENG-100"

    def test_issue_with_children(self):
        """Test issue with children."""
        data = {
            "children": {
                "nodes": [
                    {"id": "child-001", "identifier": "ENG-124"},
                    {"id": "child-002", "identifier": "ENG-125"},
                ]
            }
        }
        issue = LinearIssue(data)
        children = issue.get_children_identifiers()
        assert len(children) == 2
        assert "ENG-124" in children
        assert "ENG-125" in children

    def test_issue_empty_data(self):
        """Test LinearIssue with empty data."""
        issue = LinearIssue({})
        assert issue.get_id() == ""
        assert issue.get_identifier() == ""
        assert issue.get_title() == ""
        assert issue.get_description() == ""
        assert issue.get_state() == ""
        assert issue.get_priority() == 0
        assert issue.get_priority_label() == "No Priority"
        assert issue.get_assignee().get_name() == ""
        assert issue.get_labels() == []
        assert issue.get_comments() == []
        assert issue.get_completed_at() is None
        assert issue.get_canceled_at() is None

    def test_composed_issue_info(self):
        """Test get_composed_issue_info produces expected output."""
        data = _load_mock_issue()
        issue = LinearIssue(data)
        info = issue.get_composed_issue_info()

        assert "ENG-123" in info
        assert "Implement Linear integration" in info
        assert "Project Manager" in info
        assert "Test Developer" in info
        assert "In Progress" in info
        assert "High" in info
        assert "Engineering" in info
        assert "Platform Integrations" in info
        assert "Sprint 12" in info
        assert "enhancement" in info
        assert "integration" in info
        assert "Description:" in info
        assert "Comments:" in info

    def test_composed_issue_info_minimal(self):
        """Test get_composed_issue_info with minimal data."""
        issue = LinearIssue({"identifier": "MIN-1", "title": "Minimal issue"})
        info = issue.get_composed_issue_info()

        assert "MIN-1" in info
        assert "Minimal issue" in info
        assert "Unassigned" in info

    def test_priority_labels_mapping(self):
        """Test all priority labels are defined."""
        assert PRIORITY_LABELS[0] == "No Priority"
        assert PRIORITY_LABELS[1] == "Urgent"
        assert PRIORITY_LABELS[2] == "High"
        assert PRIORITY_LABELS[3] == "Medium"
        assert PRIORITY_LABELS[4] == "Low"
