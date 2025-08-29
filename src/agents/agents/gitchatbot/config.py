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


"""Configuration for the chatbot agent."""


from core.config import BaseConfig


class GitChatbotAgentConfig:
    """Type-safe configuration class for the chatbot agent."""

    def __init__(self, base_config: BaseConfig):
        self._base_config = base_config

    def get_model(self) -> str:
        """Get the LLM model to use for the chatbot agent.

        Returns:
            Model identifier (e.g., 'openai:gpt-4o', 'google-gla:gemini-1.5-flash')
        """
        return str(
            self._base_config.get_value("agents.gitchatbot.model", "openai:gpt-4o")
        )

    def get_max_tokens(self) -> int:
        """Get the maximum tokens for agent responses.

        Returns:
            Maximum number of tokens
        """
        return int(self._base_config.get_value("agents.gitchatbot.maxTokens", 1000))

    def get_temperature(self) -> float:
        """Get the temperature setting for response generation.

        Returns:
            Temperature value between 0.0 and 1.0
        """
        return float(self._base_config.get_value("agents.gitchatbot.temperature", 0.7))

    def get_timeout_seconds(self) -> int:
        """Get the timeout for agent execution.

        Returns:
            Timeout in seconds
        """
        return int(self._base_config.get_value("agents.gitchatbot.timeoutSeconds", 60))

    def is_configured(self) -> bool:
        """Check if the chatbot agent is properly configured.

        Returns:
            True if configuration is valid
        """
        model = self.get_model()
        return bool(model and model.strip())
