from core.config import BaseConfig


class ClaudeCodeConfig(BaseConfig):
    """Typed configuration wrapper for Claude Code subagent settings."""

    def __init__(self, base_config: BaseConfig):
        # Initialize parent with the same config path
        super().__init__(base_config=base_config)

    def get_cli_path(self) -> str | None:
        """Get the Claude Code CLI path from configuration.

        Returns the path to the Claude Code CLI executable, or None if not configured.
        Can be set via CLAUDE_CODE_PATH environment variable.
        """
        cli_path = self.get_value("subagents.claude_code.cli_path", "")
        # Return None if empty string or not set
        return cli_path if cli_path else None

    def is_configured(self) -> bool:
        """Check if Claude Code CLI path is configured."""
        return self.get_cli_path() is not None
