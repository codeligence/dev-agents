"""Tests for the Claude Code subagent configuration accessors."""

from pathlib import Path
import tempfile

import pytest

pytest.importorskip("claude_agent_sdk")

from agents.subagents.claude_code import ClaudeCodeConfig  # noqa: E402
from core.config import BaseConfig  # noqa: E402


def _config_from_yaml(yaml_text: str) -> ClaudeCodeConfig:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as handle:
        handle.write(yaml_text)
        temp_path = handle.name
    try:
        return ClaudeCodeConfig(BaseConfig(temp_path))
    finally:
        Path(temp_path).unlink()


class TestClaudeCodeConfigModel:
    """The subagent must never inherit the host user's CLI model preference."""

    def test_bundled_default_provides_a_model(self):
        config = ClaudeCodeConfig(BaseConfig())
        model = config.get_model()
        assert model, "a model must always be configured for the spawned CLI"
        assert model.startswith("claude-")

    def test_get_model_reads_configured_value(self):
        config = _config_from_yaml(
            "subagents:\n  claude_code:\n    model: 'claude-opus-5'\n"
        )
        assert config.get_model() == "claude-opus-5"

    @pytest.mark.parametrize("configured", ["", None])
    def test_get_model_returns_none_when_unset(self, configured):
        value = "''" if configured == "" else "null"
        config = _config_from_yaml(f"subagents:\n  claude_code:\n    model: {value}\n")
        assert config.get_model() is None

    def test_get_model_missing_section_returns_none(self):
        config = _config_from_yaml("subagents:\n  coderesearch:\n    model: 'x'\n")
        assert config.get_model() is None
