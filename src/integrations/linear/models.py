from typing import Any

# Linear priority mapping: 0=No priority, 1=Urgent, 2=High, 3=Medium, 4=Low
PRIORITY_LABELS = {
    0: "No Priority",
    1: "Urgent",
    2: "High",
    3: "Medium",
    4: "Low",
}


class LinearUser:
    """Represents a Linear user."""

    def __init__(self, data: dict[str, Any] | None):
        """Initialize with Linear API user data.

        Args:
            data: Linear API user data dictionary or None
        """
        self.data = data or {}

    def get_name(self) -> str:
        """Get user's display name."""
        return str(self.data.get("name", ""))

    def get_email(self) -> str:
        """Get user's email address."""
        return str(self.data.get("email", ""))

    def get_id(self) -> str:
        """Get user's ID."""
        return str(self.data.get("id", ""))


class LinearLabel:
    """Represents a Linear label."""

    def __init__(self, data: dict[str, Any]):
        """Initialize with Linear API label data.

        Args:
            data: Linear API label data dictionary
        """
        self.data = data

    def get_name(self) -> str:
        """Get label name."""
        return str(self.data.get("name", ""))

    def get_color(self) -> str:
        """Get label color."""
        return str(self.data.get("color", ""))


class LinearComment:
    """Represents a Linear issue comment."""

    def __init__(self, data: dict[str, Any]):
        """Initialize with Linear API comment data.

        Args:
            data: Linear API comment data dictionary
        """
        self.data = data

    def get_body(self) -> str:
        """Get comment body (Markdown)."""
        return str(self.data.get("body", ""))

    def get_user(self) -> LinearUser:
        """Get comment author."""
        return LinearUser(self.data.get("user"))

    def get_created_at(self) -> str:
        """Get creation timestamp."""
        return str(self.data.get("createdAt", ""))


class LinearIssue:
    """Represents a Linear issue."""

    def __init__(self, issue_data: dict[str, Any]):
        """Initialize with Linear API issue data.

        Args:
            issue_data: Linear API issue data dictionary
        """
        self.issue_data = issue_data

    def get_id(self) -> str:
        """Get issue UUID."""
        return str(self.issue_data.get("id", ""))

    def get_identifier(self) -> str:
        """Get human-readable identifier (e.g., 'ENG-123')."""
        return str(self.issue_data.get("identifier", ""))

    def get_title(self) -> str:
        """Get issue title."""
        return str(self.issue_data.get("title", ""))

    def get_description(self) -> str:
        """Get issue description (Markdown)."""
        return str(self.issue_data.get("description", "") or "")

    def get_state(self) -> str:
        """Get workflow state name."""
        state = self.issue_data.get("state")
        if isinstance(state, dict):
            return str(state.get("name", ""))
        return ""

    def get_state_type(self) -> str:
        """Get workflow state type (triage/backlog/unstarted/started/completed/canceled)."""
        state = self.issue_data.get("state")
        if isinstance(state, dict):
            return str(state.get("type", ""))
        return ""

    def get_priority(self) -> int:
        """Get issue priority (0=No priority, 1=Urgent, 2=High, 3=Medium, 4=Low)."""
        return int(self.issue_data.get("priority", 0))

    def get_priority_label(self) -> str:
        """Get human-readable priority label."""
        return PRIORITY_LABELS.get(self.get_priority(), "Unknown")

    def get_assignee(self) -> LinearUser:
        """Get the assignee of the issue."""
        return LinearUser(self.issue_data.get("assignee"))

    def get_creator(self) -> LinearUser:
        """Get the creator of the issue."""
        return LinearUser(self.issue_data.get("creator"))

    def get_labels(self) -> list[LinearLabel]:
        """Get issue labels."""
        labels_data = self.issue_data.get("labels", {})
        nodes = labels_data.get("nodes", []) if isinstance(labels_data, dict) else []
        return [LinearLabel(label) for label in nodes]

    def get_comments(self) -> list[LinearComment]:
        """Get issue comments."""
        comments_data = self.issue_data.get("comments", {})
        nodes = (
            comments_data.get("nodes", []) if isinstance(comments_data, dict) else []
        )
        return [LinearComment(comment) for comment in nodes]

    def get_team_name(self) -> str:
        """Get the team name."""
        team = self.issue_data.get("team")
        if isinstance(team, dict):
            return str(team.get("name", ""))
        return ""

    def get_team_key(self) -> str:
        """Get the team key."""
        team = self.issue_data.get("team")
        if isinstance(team, dict):
            return str(team.get("key", ""))
        return ""

    def get_project_name(self) -> str:
        """Get the project name."""
        project = self.issue_data.get("project")
        if isinstance(project, dict):
            return str(project.get("name", ""))
        return ""

    def get_cycle_name(self) -> str:
        """Get the cycle name."""
        cycle = self.issue_data.get("cycle")
        if isinstance(cycle, dict):
            return str(cycle.get("name", ""))
        return ""

    def get_estimate(self) -> float | None:
        """Get story point estimate."""
        return self.issue_data.get("estimate")

    def get_due_date(self) -> str | None:
        """Get due date."""
        return self.issue_data.get("dueDate")

    def get_created_at(self) -> str:
        """Get creation timestamp."""
        return str(self.issue_data.get("createdAt", ""))

    def get_updated_at(self) -> str:
        """Get last update timestamp."""
        return str(self.issue_data.get("updatedAt", ""))

    def get_completed_at(self) -> str | None:
        """Get completion timestamp."""
        return self.issue_data.get("completedAt")

    def get_canceled_at(self) -> str | None:
        """Get cancelation timestamp."""
        return self.issue_data.get("canceledAt")

    def get_url(self) -> str:
        """Get web URL of the issue."""
        return str(self.issue_data.get("url", ""))

    def get_parent_identifier(self) -> str | None:
        """Get parent issue identifier."""
        parent = self.issue_data.get("parent")
        if isinstance(parent, dict):
            return str(parent.get("identifier", ""))
        return None

    def get_children_identifiers(self) -> list[str]:
        """Get child issue identifiers."""
        children = self.issue_data.get("children", {})
        nodes = children.get("nodes", []) if isinstance(children, dict) else []
        return [str(child.get("identifier", "")) for child in nodes if child]

    def get_composed_issue_info(self) -> str:
        """Get composed issue information for AI context.

        Returns:
            Formatted issue information string
        """
        assignee = self.get_assignee()
        assignee_name = assignee.get_name() or "Unassigned"

        creator = self.get_creator()
        creator_name = creator.get_name() or "Unknown"

        composed_info = f"Issue {self.get_identifier()}: {self.get_title()}\n"
        composed_info += f"Creator: {creator_name}\n"
        composed_info += f"Assignee: {assignee_name}\n"
        composed_info += f"State: {self.get_state()}\n"
        composed_info += f"Priority: {self.get_priority_label()}\n"

        if self.get_team_name():
            composed_info += f"Team: {self.get_team_name()}\n"

        if self.get_project_name():
            composed_info += f"Project: {self.get_project_name()}\n"

        if self.get_cycle_name():
            composed_info += f"Cycle: {self.get_cycle_name()}\n"

        if self.get_estimate() is not None:
            composed_info += f"Estimate: {self.get_estimate()}\n"

        if self.get_due_date():
            composed_info += f"Due Date: {self.get_due_date()}\n"

        composed_info += f"Created: {self.get_created_at()}\n"
        composed_info += f"Updated: {self.get_updated_at()}\n"

        if self.get_completed_at():
            composed_info += f"Completed: {self.get_completed_at()}\n"

        if self.get_canceled_at():
            composed_info += f"Canceled: {self.get_canceled_at()}\n"

        # Labels
        labels = self.get_labels()
        if labels:
            label_names = [label.get_name() for label in labels]
            composed_info += f"Labels: {', '.join(label_names)}\n"

        # Parent issue
        parent_id = self.get_parent_identifier()
        if parent_id:
            composed_info += f"Parent: {parent_id}\n"

        # Sub-issues
        children = self.get_children_identifiers()
        if children:
            composed_info += f"Sub-issues: {', '.join(children)}\n"

        # URL
        if self.get_url():
            composed_info += f"URL: {self.get_url()}\n"

        # Description
        description = self.get_description()
        composed_info += f"\nDescription:\n{description}\n" if description else ""

        # Comments
        comments = self.get_comments()
        if comments:
            composed_info += "\nComments:\n"
            for comment in comments:
                author = comment.get_user()
                author_name = author.get_name() or "Unknown"
                created = comment.get_created_at()
                body = comment.get_body()
                composed_info += f"  - {author_name} on {created}:\n"
                # Indent comment body
                indented_body = body.replace("\n", "\n      ")
                composed_info += f"      {indented_body}\n"

        return composed_info
