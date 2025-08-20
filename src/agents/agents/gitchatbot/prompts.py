from core.prompts import BasePrompts


class GitChatbotAgentPrompts:
    """Prompts loader for the chatbot agent."""

    def __init__(self, base_prompts: BasePrompts):
        self._base_prompts = base_prompts

    def get_chatbot_prompt(self) -> str:
        """Get the initial system prompt for the chatbot agent."""
        return self._base_prompts.get_prompt('agents.chatbot.initial', '')
