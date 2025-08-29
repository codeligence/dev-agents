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


"""Data models for the chatbot agent."""

from dataclasses import dataclass

from core.storage import BaseStorage


@dataclass
class ChatbotContext:
    """Context information for chatbot agent operations.

    All fields are optional to support partial context updates.
    """

    issue_id: str | None = None
    pull_request_id: str | None = None
    source_branch_name: str | None = None
    target_branch_name: str | None = None
    source_commit_hash: str | None = None
    target_commit_hash: str | None = None

    def __post_init__(self) -> None:
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
            "source_branch_name": context.source_branch_name,
            "target_branch_name": context.target_branch_name,
            "source_commit_hash": context.source_commit_hash,
            "target_commit_hash": context.target_commit_hash,
        }
        self.storage.set(self.get_storage_key(), context_data)
        self.context = context
