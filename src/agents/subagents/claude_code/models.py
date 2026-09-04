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

    def get_model(self) -> str | None:
        """Get the model the Claude Code CLI subprocess must use.

        Returning ``None`` would let the spawned CLI fall back to the host
        user's personal ``~/.claude/settings.json`` model preference, which is
        not a valid deployment default for a server product. Configurable via
        the CLAUDE_CODE_MODEL environment variable.
        """
        model = self.get_value("subagents.claude_code.model", "")
        return model if model else None

    def is_configured(self) -> bool:
        """Check if Claude Code CLI path is configured."""
        return self.get_cli_path() is not None
