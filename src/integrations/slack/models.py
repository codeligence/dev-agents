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

    def get_max_connection_failures(self) -> int:
        """Get the maximum number of consecutive connection failures before shutdown."""
        return int(self._base_config.get_value("slack.bot.maxConnectionFailures", 5))

    def is_configured(self) -> bool:
        """Check if all required Slack configuration is present."""
        return bool(self.get_bot_token() and self.get_app_token())
