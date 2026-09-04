"""Tests for MattermostService — WebSocket event handling without real connections."""

from unittest.mock import AsyncMock, patch
import json
import os
import time

import pytest

from integrations.platforms.mattermost import MattermostService


class TestMattermostService:
    def _make_service(self, **env_overrides):
        env = {
            "MATTERMOST_URL": "https://mm.example.com",
            "MATTERMOST_TOKEN": "test-token",
            **env_overrides,
        }
        with patch.dict(os.environ, env, clear=False):
            return MattermostService()

    def test_init(self):
        svc = self._make_service()
        assert svc.name == "mattermost"
        assert svc._base_url == "https://mm.example.com"
        assert svc._token == "test-token"

    def test_init_strips_trailing_slash(self):
        svc = self._make_service(MATTERMOST_URL="https://mm.example.com/")
        assert svc._base_url == "https://mm.example.com"

    def test_init_lowercases_scheme(self):
        """Scheme is normalized once so downstream checks can be case-sensitive."""
        svc = self._make_service(MATTERMOST_URL="HTTPS://mm.example.com/")
        assert svc._base_url == "https://mm.example.com"

    def test_ws_url_for_https(self):
        svc = self._make_service(MATTERMOST_URL="https://mm.example.com")
        assert svc._ws_url() == "wss://mm.example.com/api/v4/websocket"

    def test_ws_url_for_uppercase_https(self):
        """Uppercase HTTPS:// must still produce a valid wss:// WebSocket URL."""
        svc = self._make_service(MATTERMOST_URL="HTTPS://mm.example.com")
        assert svc._ws_url() == "wss://mm.example.com/api/v4/websocket"

    def test_ws_url_for_http(self):
        svc = self._make_service(MATTERMOST_URL="http://mm.example.com")
        assert svc._ws_url() == "ws://mm.example.com/api/v4/websocket"

    def test_headers(self):
        svc = self._make_service()
        h = svc._headers()
        assert h["Authorization"] == "Bearer test-token"
        assert h["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_connect_rejects_plaintext_url(self):
        """A http:// URL must be refused before any network/auth I/O.

        We patch ``_api_get`` and ``_ws_loop`` so any path that gets past the
        https guard would observably reach them. The guard must short-circuit
        so neither is touched.
        """
        svc = self._make_service(MATTERMOST_URL="http://mm.example.com")
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(svc, "_api_get", AsyncMock()) as mock_api,
            patch.object(svc, "_ws_loop", AsyncMock()) as mock_ws,
        ):
            assert await svc.connect() is False

        mock_api.assert_not_awaited()
        mock_ws.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_connect_allows_plaintext_with_override(self):
        """With the insecure override, connect() proceeds past the guard to
        a successful auth + WebSocket loop, returning True. This removes the
        ambiguity of asserting False on a path that fails either way.
        """
        svc = self._make_service(MATTERMOST_URL="http://mm.example.com")
        valid_me = {"id": "U1", "username": "bot"}
        with (
            patch.dict(os.environ, {"MATTERMOST_ALLOW_INSECURE": "true"}),
            patch.object(svc, "_api_get", AsyncMock(return_value=valid_me)) as mock_api,
            patch.object(svc, "_ws_loop", AsyncMock()) as mock_ws,
        ):
            assert await svc.connect() is True

        mock_api.assert_awaited_with("users/me")
        mock_ws.assert_awaited_once()
        assert svc._bot_user_id == "U1"
        assert svc._bot_username == "bot"

    @pytest.mark.asyncio
    async def test_connect_insecure_override_emits_warning(self, caplog, monkeypatch):
        """When the override is honored, a warning must name the env var so
        operators can spot accidental use of plaintext in production logs."""
        import logging as _logging

        svc = self._make_service(MATTERMOST_URL="http://mm.example.com")
        # Install a real logger for this test (conftest stubs get_logger
        # with a MagicMock at module load).
        real_logger = _logging.getLogger("test.integrations.platforms.mattermost")
        real_logger.propagate = True
        monkeypatch.setattr(svc, "logger", real_logger)

        valid_me = {"id": "U1", "username": "bot"}
        caplog.set_level(_logging.WARNING, logger=real_logger.name)
        with (
            patch.dict(os.environ, {"MATTERMOST_ALLOW_INSECURE": "true"}),
            patch.object(svc, "_api_get", AsyncMock(return_value=valid_me)),
            patch.object(svc, "_ws_loop", AsyncMock()),
        ):
            await svc.connect()

        warnings = [
            r
            for r in caplog.records
            if r.levelno == _logging.WARNING and r.name == real_logger.name
        ]
        assert warnings, "expected an insecure-override warning"
        msg = warnings[-1].getMessage()
        assert "MATTERMOST_ALLOW_INSECURE" in msg
        assert "insecure" in msg.lower()

    def test_format_message_strips_image_markdown(self):
        result = MattermostService._format_message("Look: ![alt](http://img.png) here")
        assert result == "Look: http://img.png here"
        assert "![" not in result

    def test_format_message_plain_text(self):
        result = MattermostService._format_message("Just text")
        assert result == "Just text"

    # -- Dedup tests ----------------------------------------------------------

    def test_prune_seen_under_limit(self):
        svc = self._make_service()
        svc._seen_posts = {"a": time.time()}
        svc._prune_seen()
        assert "a" in svc._seen_posts

    def test_prune_seen_removes_expired(self):
        svc = self._make_service()
        svc._SEEN_MAX = 2
        old = time.time() - 600  # 10 min ago, TTL is 5 min
        svc._seen_posts = {"old1": old, "old2": old, "new": time.time()}
        svc._prune_seen()
        assert "old1" not in svc._seen_posts
        assert "new" in svc._seen_posts

    # -- WS event handling ----------------------------------------------------

    @pytest.mark.asyncio
    async def test_handle_ws_event_ignores_non_posted(self):
        svc = self._make_service()
        svc._dispatch_message = AsyncMock()
        await svc._handle_ws_event({"event": "typing"})
        svc._dispatch_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_ws_event_ignores_own_messages(self):
        svc = self._make_service()
        svc._bot_user_id = "bot123"
        svc._dispatch_message = AsyncMock()

        event = {
            "event": "posted",
            "data": {
                "post": json.dumps(
                    {
                        "id": "p1",
                        "user_id": "bot123",
                        "channel_id": "ch1",
                        "message": "I said this",
                    }
                ),
                "channel_type": "D",
            },
        }
        await svc._handle_ws_event(event)
        svc._dispatch_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_ws_event_ignores_system_posts(self):
        svc = self._make_service()
        svc._bot_user_id = "bot123"
        svc._dispatch_message = AsyncMock()

        event = {
            "event": "posted",
            "data": {
                "post": json.dumps(
                    {
                        "id": "p2",
                        "user_id": "user1",
                        "channel_id": "ch1",
                        "message": "joined",
                        "type": "system_join_channel",
                    }
                ),
                "channel_type": "O",
            },
        }
        await svc._handle_ws_event(event)
        svc._dispatch_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_ws_event_dispatches_dm(self):
        svc = self._make_service()
        svc._bot_user_id = "bot123"
        svc._dispatch_message = AsyncMock()

        event = {
            "event": "posted",
            "data": {
                "post": json.dumps(
                    {
                        "id": "p3",
                        "user_id": "user1",
                        "channel_id": "ch1",
                        "message": "Hello bot",
                    }
                ),
                "channel_type": "D",
                "sender_name": "@alice",
            },
        }
        await svc._handle_ws_event(event)
        svc._dispatch_message.assert_called_once()
        msg = svc._dispatch_message.call_args[0][0]
        assert msg.content == "Hello bot"
        assert msg.platform_name == "mattermost"

    @pytest.mark.asyncio
    async def test_handle_ws_event_dedup(self):
        svc = self._make_service()
        svc._bot_user_id = "bot123"
        svc._dispatch_message = AsyncMock()

        event = {
            "event": "posted",
            "data": {
                "post": json.dumps(
                    {
                        "id": "p4",
                        "user_id": "user1",
                        "channel_id": "ch1",
                        "message": "Hello",
                    }
                ),
                "channel_type": "D",
                "sender_name": "alice",
            },
        }
        await svc._handle_ws_event(event)
        await svc._handle_ws_event(event)  # duplicate
        assert svc._dispatch_message.call_count == 1

    @pytest.mark.asyncio
    async def test_handle_ws_event_unauthorized_user(self):
        svc = self._make_service(MATTERMOST_ALLOWED_USERS="allowed-user")
        svc._bot_user_id = "bot123"
        svc._dispatch_message = AsyncMock()

        event = {
            "event": "posted",
            "data": {
                "post": json.dumps(
                    {
                        "id": "p5",
                        "user_id": "stranger",
                        "channel_id": "ch1",
                        "message": "Hi",
                    }
                ),
                "channel_type": "D",
                "sender_name": "stranger",
            },
        }
        await svc._handle_ws_event(event)
        svc._dispatch_message.assert_not_called()

    # -- Mention gating -------------------------------------------------------

    @pytest.mark.asyncio
    async def test_mention_gating_requires_mention_in_channel(self):
        svc = self._make_service(MATTERMOST_REQUIRE_MENTION="true")
        svc._bot_user_id = "bot123"
        svc._bot_username = "claw"
        svc._dispatch_message = AsyncMock()

        event = {
            "event": "posted",
            "data": {
                "post": json.dumps(
                    {
                        "id": "p6",
                        "user_id": "user1",
                        "channel_id": "ch1",
                        "message": "Hello everyone",
                    }
                ),
                "channel_type": "O",  # public channel
                "sender_name": "alice",
            },
        }
        await svc._handle_ws_event(event)
        svc._dispatch_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_mention_gating_passes_with_mention(self):
        svc = self._make_service(MATTERMOST_REQUIRE_MENTION="true")
        svc._bot_user_id = "bot123"
        svc._bot_username = "claw"
        svc._dispatch_message = AsyncMock()

        event = {
            "event": "posted",
            "data": {
                "post": json.dumps(
                    {
                        "id": "p7",
                        "user_id": "user1",
                        "channel_id": "ch1",
                        "message": "@claw what is this?",
                    }
                ),
                "channel_type": "O",
                "sender_name": "alice",
            },
        }
        await svc._handle_ws_event(event)
        svc._dispatch_message.assert_called_once()
        msg = svc._dispatch_message.call_args[0][0]
        assert "@claw" not in msg.content  # mention stripped

    @pytest.mark.asyncio
    async def test_mention_gating_free_channel(self):
        svc = self._make_service(
            MATTERMOST_REQUIRE_MENTION="true",
            MATTERMOST_FREE_RESPONSE_CHANNELS="ch-free",
        )
        svc._bot_user_id = "bot123"
        svc._bot_username = "claw"
        svc._dispatch_message = AsyncMock()

        event = {
            "event": "posted",
            "data": {
                "post": json.dumps(
                    {
                        "id": "p8",
                        "user_id": "user1",
                        "channel_id": "ch-free",
                        "message": "No mention needed",
                    }
                ),
                "channel_type": "O",
                "sender_name": "alice",
            },
        }
        # Env vars are read at event-handling time, so patch must be active
        with patch.dict(
            os.environ,
            {
                "MATTERMOST_REQUIRE_MENTION": "true",
                "MATTERMOST_FREE_RESPONSE_CHANNELS": "ch-free",
            },
        ):
            await svc._handle_ws_event(event)
        svc._dispatch_message.assert_called_once()
