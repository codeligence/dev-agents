"""Data models for the chatbot agent."""

from dataclasses import dataclass, field

from core.storage import BaseStorage


@dataclass
class ChatbotContext:
    """Context information for chatbot agent operations.

    All fields are optional to support partial context updates.
    """

    issue_id: str | None = None
    pull_request_id: str | None = None
    source_git_ref: str | None = None
    target_git_ref: str | None = None
    artifact_ids: list[str] = field(default_factory=list)
    project: str | None = None

    def __post_init__(self) -> None:
        """Auto-populate target_git_ref if only source is provided and set default project."""
        if self.source_git_ref and not self.target_git_ref:
            self.target_git_ref = self.source_git_ref
        if not self.project:
            self.project = "default"


@dataclass
class PersistentAgentDeps:
    """Dependencies for persistent chatbot agent using Pydantic AI.

    Contains all dependencies needed for state persistence across agent runs.
    This is used as the deps_type for the Pydantic AI agent.
    """

    execution_id: str
    storage: BaseStorage
    context: ChatbotContext | None = None

    def get_storage_key(self) -> str:
        """Get the storage key for this execution context.

        Returns:
            Storage key based on execution_id
        """
        return f"chatbot_context_{self.execution_id}"

    def load_context(self) -> ChatbotContext:
        """Load context from storage or create new one.

        Returns:
            ChatbotContext instance loaded from storage or new empty context
        """
        stored_data = self.storage.get(self.get_storage_key())
        if stored_data:
            return ChatbotContext(**stored_data)
        return ChatbotContext()

    def save_context(self, context: ChatbotContext) -> None:
        """Save context to storage.

        Args:
            context: ChatbotContext to save
        """
        # Convert dataclass to dict for JSON serialization
        context_data = {
            "issue_id": context.issue_id,
            "pull_request_id": context.pull_request_id,
            "source_git_ref": context.source_git_ref,
            "target_git_ref": context.target_git_ref,
            "artifact_ids": context.artifact_ids,
            "project": context.project,
        }
        self.storage.set(self.get_storage_key(), context_data)
        self.context = context
