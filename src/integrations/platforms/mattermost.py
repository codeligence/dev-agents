"""Mattermost platform service for dev-agents-claw.

Connects via REST API (v4) and WebSocket for real-time events.
Ported from hermes-agent/gateway/platforms/mattermost.py (MIT).

Environment variables:
    MATTERMOST_ENABLED              — Must be true to activate this platform
    MATTERMOST_URL                  — Server URL (https:// required)
    MATTERMOST_ALLOW_INSECURE       — Allow plaintext http:// URL (dev only)
    MATTERMOST_TOKEN                — Bot token or personal-access token
    MATTERMOST_REPLY_MODE           — "thread" to nest replies, "off" for flat (default: off)
    MATTERMOST_REQUIRE_MENTION      — Require @mention in channels (default: true)
    MATTERMOST_FREE_RESPONSE_CHANNELS — Channel IDs where bot responds without mention
    MATTERMOST_ALLOWED_USERS        — Comma-separated allowed user IDs (optional)

Dependencies: aiohttp>=3.13.3,<4
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import asyncio
import json
import os
import re
import time

from integrations.platforms.base import BasePlatformService, PlatformMessage

# Mattermost post size limit (4000 is practical for readability).
MAX_POST_LENGTH = 4000

# Channel type codes returned by the Mattermost API.
_CHANNEL_TYPE_MAP = {
    "D": "dm",
    "G": "group",
    "P": "group",
    "O": "channel",
}

# Reconnect parameters (exponential backoff).
_RECONNECT_BASE_DELAY = 2.0
_RECONNECT_MAX_DELAY = 60.0
_RECONNECT_JITTER = 0.2


class MattermostService(BasePlatformService):
    """Mattermost platform service using REST API + WebSocket."""

    supports_updates = True

    def __init__(self) -> None:
        super().__init__("mattermost")

        self._base_url: str = self._normalize_base_url(os.getenv("MATTERMOST_URL", ""))
        self._token: str = os.getenv("MATTERMOST_TOKEN", "")
        self._reply_mode: str = os.getenv("MATTERMOST_REPLY_MODE", "off").lower()

        self._allowed_users = self.get_authorized_ids("MATTERMOST_ALLOWED_USERS")

        self._bot_user_id: str = ""
        self._bot_username: str = ""

        # aiohttp handles
        self._session: Any = None
        self._ws: Any = None
        self._closing = False

        # Dedup cache: post_id -> timestamp
        self._seen_posts: dict[str, float] = {}
        self._SEEN_MAX = 2000
        self._SEEN_TTL = 300  # 5 min

    # -- URL helpers ----------------------------------------------------------

    @staticmethod
    def _normalize_base_url(raw: str) -> str:
        """Normalize the configured base URL once at init.

        Strips trailing slashes and lower-cases the scheme so downstream code
        can do case-sensitive comparisons (``startswith("https://")``) and
        case-sensitive ``re.sub`` replacements without surprises.
        """
        raw = raw.strip().rstrip("/")
        if "://" in raw:
            scheme, rest = raw.split("://", 1)
            return f"{scheme.lower()}://{rest}"
        return raw

    def _ws_url(self) -> str:
        """Return the WebSocket URL for the normalized base URL.

        ``https://`` becomes ``wss://`` and ``http://`` becomes ``ws://``.
        Relies on ``_normalize_base_url`` having lower-cased the scheme.
        """
        return re.sub(r"^http", "ws", self._base_url) + "/api/v4/websocket"

    # -- HTTP helpers ---------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }

    async def _api_get(self, path: str) -> dict[str, Any]:
        import aiohttp

        url = f"{self._base_url}/api/v4/{path.lstrip('/')}"
        try:
            async with self._session.get(
                url,
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    self.logger.error(
                        "API GET %s -> %s: %s", path, resp.status, body[:200]
                    )
                    return {}
                data: dict[str, Any] = await resp.json()
                return data
        except Exception as exc:
            self.logger.error("API GET %s error: %s", path, exc)
            return {}

    async def _api_post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        import aiohttp

        url = f"{self._base_url}/api/v4/{path.lstrip('/')}"
        try:
            async with self._session.post(
                url,
                headers=self._headers(),
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    self.logger.error(
                        "API POST %s -> %s: %s", path, resp.status, body[:200]
                    )
                    return {}
                data: dict[str, Any] = await resp.json()
                return data
        except Exception as exc:
            self.logger.error("API POST %s error: %s", path, exc)
            return {}

    async def _api_put(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        import aiohttp

        url = f"{self._base_url}/api/v4/{path.lstrip('/')}"
        try:
            async with self._session.put(
                url,
                headers=self._headers(),
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    self.logger.error(
                        "API PUT %s -> %s: %s", path, resp.status, body[:200]
                    )
                    return {}
                data: dict[str, Any] = await resp.json()
                return data
        except Exception as exc:
            self.logger.error("API PUT %s error: %s", path, exc)
            return {}

    # -- BasePlatformService interface ----------------------------------------

    async def connect(self) -> bool:
        """Authenticate, then run the WebSocket listener (blocks until disconnect)."""
        import aiohttp

        if not self._base_url or not self._token:
            self.logger.error("URL or token not configured")
            return False

        # The bot token is sent over both the REST and WebSocket connections.
        # A plaintext http:// URL would leak it, so refuse unless the operator
        # explicitly opts into an insecure connection for local development.
        # _base_url is normalized at init, so a case-sensitive check is safe.
        if not self._base_url.startswith("https://"):
            if self.env_flag("MATTERMOST_ALLOW_INSECURE"):
                self.logger.warning(
                    "MATTERMOST_URL is not https:// — sending the token over an "
                    "insecure connection because MATTERMOST_ALLOW_INSECURE is set"
                )
            else:
                self.logger.error(
                    "MATTERMOST_URL must use https:// (got %r). The auth token "
                    "would otherwise be sent in plaintext. Set "
                    "MATTERMOST_ALLOW_INSECURE=true to override for local dev.",
                    self._base_url,
                )
                return False

        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
        )
        self._closing = False

        # Verify credentials and get bot identity
        me = await self._api_get("users/me")
        if not me or "id" not in me:
            self.logger.error(
                "Authentication failed — check MATTERMOST_TOKEN and MATTERMOST_URL"
            )
            await self._session.close()
            return False

        self._bot_user_id = me["id"]
        self._bot_username = me.get("username", "")
        self.logger.info(
            "Authenticated as @%s (%s) on %s",
            self._bot_username,
            self._bot_user_id,
            self._base_url,
        )

        # Run WebSocket loop (blocks until closed/error)
        await self._ws_loop()
        return True

    async def disconnect(self) -> None:
        self._closing = True
        if self._ws:
            await self._ws.close()
            self._ws = None
        if self._session and not self._session.closed:
            await self._session.close()
        self.logger.info("Disconnected")

    async def send_response(
        self, chat_id: str, thread_id: str, text: str
    ) -> str | None:
        """Send a message (or multiple chunks) to a channel.

        Returns the post ID of the last sent chunk on success so the context
        can edit it later for status updates.  Returns ``None`` on failure.
        """
        if not text:
            return None

        formatted = self._format_message(text)
        chunks = self.truncate_message(formatted, MAX_POST_LENGTH)

        last_post_id: str | None = None

        for chunk in chunks:
            payload: dict[str, Any] = {
                "channel_id": chat_id,
                "message": chunk,
            }
            if thread_id and self._reply_mode == "thread":
                payload["root_id"] = thread_id

            data = await self._api_post("posts", payload)
            if not data or "id" not in data:
                self.logger.error("Failed to create post in %s", chat_id)
                return None
            last_post_id = str(data["id"])

        return last_post_id

    async def update_response(self, _chat_id: str, message_id: str, text: str) -> bool:
        """Edit an existing Mattermost post in place.

        Returns ``False`` if the new text exceeds ``MAX_POST_LENGTH`` or the
        edit API call fails — the caller then falls back to sending a fresh
        message.
        """
        if not text:
            return False

        formatted = self._format_message(text)
        if len(formatted) > MAX_POST_LENGTH:
            return False

        payload = {"id": message_id, "message": formatted}
        data = await self._api_put(f"posts/{message_id}/patch", payload)
        if not data or "id" not in data:
            self.logger.warning("Failed to edit post %s", message_id)
            return False
        return True

    # -- WebSocket ------------------------------------------------------------

    async def _ws_loop(self) -> None:
        """Connect to WS and listen, reconnecting on failure."""
        delay = _RECONNECT_BASE_DELAY
        while not self._closing:
            try:
                await self._ws_connect_and_listen()
                delay = _RECONNECT_BASE_DELAY
            except asyncio.CancelledError:
                return
            except Exception as exc:
                if self._closing:
                    return
                self.logger.warning("WS error: %s — reconnecting in %.0fs", exc, delay)

            if self._closing:
                return

            import random

            jitter = delay * _RECONNECT_JITTER * random.random()  # nosec B311
            await asyncio.sleep(delay + jitter)
            delay = min(delay * 2, _RECONNECT_MAX_DELAY)

    async def _ws_connect_and_listen(self) -> None:
        """Single WebSocket session: connect, authenticate, process events."""
        ws_url = self._ws_url()
        self.logger.info("Connecting to %s", ws_url)

        self._ws = await self._session.ws_connect(ws_url, heartbeat=30.0)

        auth_msg = {
            "seq": 1,
            "action": "authentication_challenge",
            "data": {"token": self._token},
        }
        await self._ws.send_json(auth_msg)
        self.logger.info("WebSocket connected and authenticated")

        async for raw_msg in self._ws:
            if self._closing:
                return
            if raw_msg.type in (raw_msg.type.TEXT, raw_msg.type.BINARY):
                try:
                    event = json.loads(raw_msg.data)
                except (json.JSONDecodeError, TypeError):
                    continue
                await self._handle_ws_event(event)
            elif raw_msg.type in (
                raw_msg.type.ERROR,
                raw_msg.type.CLOSE,
                raw_msg.type.CLOSING,
                raw_msg.type.CLOSED,
            ):
                self.logger.info("WebSocket closed (%s)", raw_msg.type)
                break

    # -- Event handling -------------------------------------------------------

    async def _handle_ws_event(self, event: dict[str, Any]) -> None:
        """Process a single WebSocket event."""
        if event.get("event") != "posted":
            return

        data = event.get("data", {})
        raw_post_str = data.get("post")
        if not raw_post_str:
            return

        try:
            post = json.loads(raw_post_str)
        except (json.JSONDecodeError, TypeError):
            return

        # Ignore own messages and system posts
        if post.get("user_id") == self._bot_user_id:
            return
        if post.get("type"):
            return

        post_id = post.get("id", "")

        # Dedup
        self._prune_seen()
        if post_id in self._seen_posts:
            return
        self._seen_posts[post_id] = time.time()

        channel_id = post.get("channel_id", "")
        channel_type_raw = data.get("channel_type", "O")
        message_text = post.get("message", "")

        # Mention-gating for non-DM channels
        if channel_type_raw != "D":
            require_mention = self.env_flag("MATTERMOST_REQUIRE_MENTION", default=True)

            # get_authorized_ids returns None when the env var is unset/empty;
            # treat that as "no free channels".
            free_channels = (
                self.get_authorized_ids("MATTERMOST_FREE_RESPONSE_CHANNELS") or set()
            )
            is_free_channel = channel_id in free_channels

            mention_patterns = [
                f"@{self._bot_username}",
                f"@{self._bot_user_id}",
            ]
            has_mention = any(
                p.lower() in message_text.lower() for p in mention_patterns
            )

            if require_mention and not is_free_channel and not has_mention:
                return

            # Strip @mention from message text
            if has_mention:
                for pattern in mention_patterns:
                    message_text = re.sub(
                        re.escape(pattern),
                        "",
                        message_text,
                        flags=re.IGNORECASE,
                    ).strip()

        # Authorization check
        sender_id = post.get("user_id", "")
        if self._allowed_users is not None and sender_id not in self._allowed_users:
            self.logger.info("Ignoring message from unauthorized user: %s", sender_id)
            return

        sender_name = data.get("sender_name", "").lstrip("@") or sender_id
        # For top-level posts (no root_id) use the post's own id as the thread
        # anchor. Mattermost replies carry that post id as their root_id, so
        # context continuity is preserved while unrelated top-level mentions
        # in the same channel get distinct execution ids.
        thread_id = post.get("root_id") or post.get("id") or ""

        message = PlatformMessage(
            user_name=sender_name,
            user_id=sender_id,
            content=message_text,
            date=datetime.now(UTC),
            thread_id=thread_id,
            channel_id=channel_id,
            platform_name="mattermost",
        )

        self.logger.info(
            "New message from @%s (%s) in %s", sender_name, sender_id, channel_id
        )
        self.logger.debug(
            "Message content from %s in %s: %s",
            sender_id,
            channel_id,
            message_text[:80],
        )
        await self._dispatch_message(message)

    # -- Helpers --------------------------------------------------------------

    @staticmethod
    def _format_message(content: str) -> str:
        """Strip image markdown into plain links (Mattermost renders URLs as previews)."""
        return re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r"\2", content)

    def _prune_seen(self) -> None:
        """Remove expired entries from the dedup cache."""
        if len(self._seen_posts) < self._SEEN_MAX:
            return
        now = time.time()
        self._seen_posts = {
            pid: ts for pid, ts in self._seen_posts.items() if now - ts < self._SEEN_TTL
        }
