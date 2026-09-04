"""Tests for the ClaudeAgentOptions the Claude Code subagent builds."""

from typing import Any
from unittest.mock import patch

import pytest

pytest.importorskip("claude_agent_sdk")

from claude_agent_sdk.types import (  # noqa: E402
    PermissionResultAllow,
    PermissionResultDeny,
)

from agents.subagents.claude_code import ClaudeCodeSubagent  # noqa: E402


class _FakeClient:
    """Minimal ClaudeSDKClient stand-in that records the options it got."""

    captured: Any = None

    def __init__(self, options: Any) -> None:
        type(self).captured = options

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *_exc: Any) -> bool:
        return False

    async def query(self, _prompt: str) -> None:
        return None

    async def receive_response(self):  # type: ignore[no-untyped-def]
        return
        yield  # pragma: no cover - makes this an async generator


@pytest.fixture
def options() -> Any:
    subagent = ClaudeCodeSubagent()
    with patch(
        "agents.subagents.claude_code.claude_code_subagent.ClaudeSDKClient",
        _FakeClient,
    ):
        import asyncio

        asyncio.run(subagent.query(formatted_query="hi", repo_path="/tmp"))
    return _FakeClient.captured


class TestClaudeCodeSubagentOptions:
    def test_model_is_set_explicitly(self, options):
        """Without an explicit model the CLI inherits ~/.claude/settings.json."""
        assert options.model
        assert options.model.startswith("claude-")

    def test_allowed_tools_does_not_shadow_permission_callback(self, options):
        """Any allowed_tools entry auto-approves before can_use_tool is consulted."""
        assert options.allowed_tools == []
        assert callable(options.can_use_tool)

    def test_write_tools_stay_denied(self, options):
        assert set(options.disallowed_tools) == {"Write", "Edit"}

    def test_repo_settings_are_not_honoured(self, options):
        """A .claude/settings.json in the analysed repo must not configure us.

        Project/local scopes can carry `permissions.allow` (auto-approved
        before can_use_tool) and `hooks` (run outside it entirely).
        """
        assert options.setting_sources == ["user"]

    def test_permission_callback_is_bound_to_the_repo(self, options):
        """The callback must confine paths to the repo_path it was given."""
        import asyncio

        async def _check(tool: str, payload: dict[str, Any]) -> Any:
            return await options.can_use_tool(tool, payload, None)

        outside = asyncio.run(_check("Read", {"file_path": "/etc/passwd"}))
        assert isinstance(outside, PermissionResultDeny)

        inside = asyncio.run(_check("Read", {"file_path": "/tmp/notes.md"}))
        assert isinstance(inside, PermissionResultAllow)
