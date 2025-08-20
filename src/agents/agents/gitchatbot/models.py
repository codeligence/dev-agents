"""Data models for the chatbot agent."""

from dataclasses import dataclass
from typing import Optional

from core.storage import BaseStorage


@dataclass
class ChatbotContext:
    """Context information for chatbot agent operations.

    All fields are optional to support partial context updates.
    """
    issue_id: Optional[str] = None
    pull_request_id: Optional[str] = None
    source_branch_name: Optional[str] = None
    target_branch_name: Optional[str] = None
    source_commit_hash: Optional[str] = None
    target_commit_hash: Optional[str] = None

    def __post_init__(self):
        """Auto-populate target_branch_name if only source is provided."""
        if self.source_branch_name and not self.target_branch_name:
            self.target_branch_name = self.source_branch_name


@dataclass
class PersistentAgentDeps:
    """Dependencies for persistent chatbot agent using Pydantic AI.

    Contains all dependencies needed for state persistence across agent runs.
    This is used as the deps_type for the Pydantic AI agent.
    """
    execution_id: str
    storage: BaseStorage
    context: Optional[ChatbotContext] = None

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
            'issue_id': context.issue_id,
            'pull_request_id': context.pull_request_id,
            'source_branch_name': context.source_branch_name,
            'target_branch_name': context.target_branch_name,
            'source_commit_hash': context.source_commit_hash,
            'target_commit_hash': context.target_commit_hash
        }
        self.storage.set(self.get_storage_key(), context_data)
        self.context = context
