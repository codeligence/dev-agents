from typing import cast

from core.config import BaseConfig


class SlackBotConfig:
    """Configuration for Slack bot service."""

    def __init__(self, base_config: BaseConfig):
        self._base_config = base_config
        self._config_data = base_config.get_config_data()

    def get_bot_token(self) -> str:
        return cast("str", self._base_config.get_value("slack.bot.botToken", ""))

    def get_app_token(self) -> str:
        return cast("str", self._base_config.get_value("slack.bot.appToken", ""))

    def get_processing_timeout(self) -> int:
        return int(self._base_config.get_value("slack.bot.processingTimeout", 6000))

    def get_always_respond(self) -> bool:
        """Get whether the bot should always respond, bypassing mention checks."""
        return self._base_config.get_bool("slack.bot.alwaysRespond", False)

    def get_welcome_message(self) -> str | None:
        """Welcome text for new Assistant threads. ``None`` to skip."""
        value = self._base_config.get_value("slack.assistant.welcomeMessage", None)
        if value is None or value == "":
            return None
        return str(value)

    def get_suggested_prompts(self) -> list[dict[str, str]]:
        """Suggested prompts surfaced when an Assistant thread starts.

        Each entry is a ``{"title": str, "message": str}`` dict, matching
        the shape Slack's ``set_suggested_prompts`` expects.
        """
        raw = self._base_config.get_value("slack.assistant.suggestedPrompts", [])
        if not isinstance(raw, list):
            return []
        prompts: list[dict[str, str]] = []
        for entry in raw:
            if not isinstance(entry, dict):
                continue
            title = entry.get("title")
            message = entry.get("message")
            if isinstance(title, str) and isinstance(message, str):
                prompts.append({"title": title, "message": message})
        return prompts

    def get_include_feedback_buttons(self) -> bool:
        """Whether to attach feedback buttons to final responses."""
        return self._base_config.get_bool(
            "slack.assistant.includeFeedbackButtons", False
        )

    def get_attachments_enabled(self) -> bool:
        """Whether message file attachments are downloaded and fed to the agent.

        Off by default: forwarding private Slack files into the LLM context is
        an explicit opt-in (set ``SLACK_ATTACHMENTS_ENABLED``).
        """
        return self._base_config.get_bool("slack.attachments.enabled", False)

    def get_attachment_max_size_mb(self) -> int:
        """Maximum size (in MB) of a binary attachment to download."""
        return int(self._base_config.get_value("slack.attachments.maxFileSizeMb", 25))

    def get_attachment_max_inline_text_kb(self) -> int:
        """Maximum size (in KB) of a text attachment to inline into the prompt.

        Much smaller than the binary cap: inlined text lands verbatim in the
        model context, so megabytes of text would blow up the prompt.
        """
        return int(self._base_config.get_value("slack.attachments.maxInlineTextKb", 50))

    def is_configured(self) -> bool:
        """Check if all required Slack configuration is present."""
        return bool(self.get_bot_token() and self.get_app_token())
