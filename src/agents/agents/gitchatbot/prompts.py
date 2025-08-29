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


from core.prompts import BasePrompts


class GitChatbotAgentPrompts:
    """Prompts loader for the chatbot agent."""

    def __init__(self, base_prompts: BasePrompts):
        self._base_prompts = base_prompts

    def get_chatbot_prompt(self) -> str:
        """Get the initial system prompt for the chatbot agent."""
        return self._base_prompts.get_prompt("agents.chatbot.initial", "")
