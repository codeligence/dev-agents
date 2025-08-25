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


"""AG-UI message implementation for converting AG-UI protocol messages to BaseMessage format."""

from datetime import datetime
from typing import Optional
from dataclasses import dataclass

from core.message import BaseMessage


@dataclass
class AGUIMessage(BaseMessage):
    """Implementation of BaseMessage for AG-UI protocol messages.
    
    Converts AG-UI Message objects to the internal BaseMessage interface
    used by the agent framework.
    """
    
    message_id: str
    role: str  # "user", "assistant", "system", "tool", "developer"
    content: str
    name: Optional[str] = None
    timestamp: Optional[datetime] = None
    thread_id: str = "default"
    
    def __post_init__(self):
        """Set default timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    def get_user_name(self) -> str:
        """Get the display name of the message sender."""
        if self.name:
            return self.name
        elif self.role == "user":
            return "User"
        elif self.role == "assistant":
            return "Assistant"
        elif self.role == "system":
            return "System"
        elif self.role == "tool":
            return "Tool"
        elif self.role == "developer":
            return "Developer"
        else:
            return self.role.title()
    
    def get_user_id(self) -> str:
        """Get the unique identifier of the message sender."""
        return f"{self.role}_{self.message_id}"
    
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
        return self.role in ("assistant", "system", "tool")


def convert_agui_messages_to_message_list(agui_messages: list, thread_id: str = "default") -> 'MessageList':
    """Convert list of AG-UI Message objects to MessageList.
    
    Args:
        agui_messages: List of AG-UI Message dictionaries/objects
        thread_id: Thread identifier for all messages
        
    Returns:
        MessageList containing converted AGUIMessage objects
    """
    from core.message import MessageList
    
    converted_messages = []
    
    for msg in agui_messages:
        # Handle both dict and object forms
        if isinstance(msg, dict):
            agui_msg = AGUIMessage(
                message_id=msg.get("id", "unknown"),
                role=msg.get("role", "user"),
                content=msg.get("content", ""),
                name=msg.get("name"),
                thread_id=thread_id
            )
        else:
            # Assume it's already a proper Message object with attributes
            agui_msg = AGUIMessage(
                message_id=getattr(msg, "id", "unknown"),
                role=getattr(msg, "role", "user"),
                content=getattr(msg, "content", ""),
                name=getattr(msg, "name", None),
                thread_id=thread_id
            )
        
        converted_messages.append(agui_msg)
    
    return MessageList(converted_messages)