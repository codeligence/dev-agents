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


"""CLI message implementation for command-line interface."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from core.message import BaseMessage


@dataclass
class CLIMessage(BaseMessage):
    """Message implementation for CLI interactions.
    
    Simple message structure for command-line user input and agent responses.
    """
    
    message_id: str
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime
    thread_id: str = "cli-session"
    
    def get_user_name(self) -> str:
        """Get the display name of the message sender."""
        if self.role == "user":
            return "CLI User"
        elif self.role == "assistant":
            return "Assistant"
        else:
            return "System"

    def get_user_id(self) -> str:
        """Get the unique identifier of the message sender."""
        if self.role == "user":
            return "cli-user"
        elif self.role == "assistant":
            return "assistant"
        else:
            return "system"

    def get_message_content(self) -> str:
        """Get the text content of the message."""
        return self.content

    def get_message_date(self) -> datetime:
        """Get the timestamp when the message was sent."""
        return self.timestamp

    def get_thread_id(self) -> str:
        """Get the unique identifier of the thread this message belongs to."""
        return self.thread_id

    def is_bot(self) -> bool:
        """Check if this message was sent by a bot."""
        return self.role == "assistant"