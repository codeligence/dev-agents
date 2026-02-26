from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class ArtifactMetadata:
    """Metadata for an artifact containing context information."""

    execution_id: str
    issue_id: str | None = None
    pull_request_id: str | None = None
    source_git_ref: str | None = None
    target_git_ref: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def generate_artifact_id(self, artifact_type: str) -> str:
        """Generate deterministic artifact ID from metadata.

        Format: {type}_{issue_id}_{pr_id}_{source_ref}_{target_ref}_{timestamp}

        Only non-empty fields are included.

        Args:
            artifact_type: Type of artifact being created

        Returns:
            Human-readable, deterministic artifact ID

        Examples:
            - changelog_1243_bugfix_1243_main_20251119130338
            - test_plan_42_feature_auth_develop_20251119140522
            - changelog_v1.2.3_v1.2.2_20251119150622
        """
        parts = [artifact_type]

        # Add non-empty fields in order
        for field_value in [
            self.issue_id,
            self.pull_request_id,
            self.source_git_ref,
            self.target_git_ref,
        ]:
            if field_value:
                parts.append(self._escape(str(field_value)))

        # Append timestamp
        timestamp = self.created_at.strftime("%Y%m%d%H%M%S")
        parts.append(timestamp)

        return "_".join(parts)

    @staticmethod
    def _escape(value: str) -> str:
        """Escape special characters for use in artifact ID.

        Args:
            value: String to escape

        Returns:
            Escaped string with special characters replaced by underscores
        """
        return value.replace("/", "_").replace("\\", "_").replace(" ", "_")

    def to_dict(self) -> dict[str, Any]:
        """Convert metadata to dictionary for JSON serialization."""
        return {
            "execution_id": self.execution_id,
            "issue_id": self.issue_id,
            "pull_request_id": self.pull_request_id,
            "source_git_ref": self.source_git_ref,
            "target_git_ref": self.target_git_ref,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ArtifactMetadata":
        """Create metadata from dictionary.

        Args:
            data: Dictionary with metadata fields

        Returns:
            ArtifactMetadata instance
        """
        return cls(
            execution_id=data["execution_id"],
            issue_id=data.get("issue_id"),
            pull_request_id=data.get("pull_request_id"),
            source_git_ref=data.get("source_git_ref"),
            target_git_ref=data.get("target_git_ref"),
            created_at=datetime.fromisoformat(data["created_at"]),
        )


@dataclass
class Artifact:
    """Artifact containing generated content and metadata."""

    artifact_id: str
    artifact_type: str
    title: str
    content: str
    metadata: ArtifactMetadata

    def to_dict(self) -> dict[str, Any]:
        """Convert artifact to dictionary for JSON serialization."""
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "title": self.title,
            "content": self.content,
            "metadata": self.metadata.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Artifact":
        """Create artifact from dictionary.

        Args:
            data: Dictionary with artifact fields

        Returns:
            Artifact instance
        """
        return cls(
            artifact_id=data["artifact_id"],
            artifact_type=data["artifact_type"],
            title=data["title"],
            content=data["content"],
            metadata=ArtifactMetadata.from_dict(data["metadata"]),
        )
