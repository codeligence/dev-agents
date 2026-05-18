"""Tests for MattermostService — WebSocket event handling without real connections."""

import json
import os
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

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

    def test_headers(self):
        svc = self._make_service()
        h = svc._headers()
        assert h["Authorization"] == "Bearer test-token"
        assert h["Content-Type"] == "application/json"

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
                "post": json.dumps({
                    "id": "p1",
                    "user_id": "bot123",
                    "channel_id": "ch1",
                    "message": "I said this",
                }),
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
                "post": json.dumps({
                    "id": "p2",
                    "user_id": "user1",
                    "channel_id": "ch1",
                    "message": "joined",
                    "type": "system_join_channel",
                }),
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
                "post": json.dumps({
                    "id": "p3",
                    "user_id": "user1",
                    "channel_id": "ch1",
                    "message": "Hello bot",
                }),
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
                "post": json.dumps({
                    "id": "p4",
                    "user_id": "user1",
                    "channel_id": "ch1",
                    "message": "Hello",
                }),
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
                "post": json.dumps({
                    "id": "p5",
                    "user_id": "stranger",
                    "channel_id": "ch1",
                    "message": "Hi",
                }),
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
                "post": json.dumps({
                    "id": "p6",
                    "user_id": "user1",
                    "channel_id": "ch1",
                    "message": "Hello everyone",
                }),
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
                "post": json.dumps({
                    "id": "p7",
                    "user_id": "user1",
                    "channel_id": "ch1",
                    "message": "@claw what is this?",
                }),
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
                "post": json.dumps({
                    "id": "p8",
                    "user_id": "user1",
                    "channel_id": "ch-free",
                    "message": "No mention needed",
                }),
                "channel_type": "O",
                "sender_name": "alice",
            },
        }
        # Env vars are read at event-handling time, so patch must be active
        with patch.dict(os.environ, {
            "MATTERMOST_REQUIRE_MENTION": "true",
            "MATTERMOST_FREE_RESPONSE_CHANNELS": "ch-free",
        }):
            await svc._handle_ws_event(event)
        svc._dispatch_message.assert_called_once()
