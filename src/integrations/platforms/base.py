"""Base platform service abstraction for non-Slack messaging platforms.

Each platform service manages its own connection (IMAP, WebSocket, polling)
and routes incoming messages through the existing ClawAgent pipeline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any
import asyncio
import contextlib
import os

from core.log import get_logger
from core.message import BaseMessage

logger = get_logger("integrations.platforms")


# ---------------------------------------------------------------------------
# PlatformMessage — concrete BaseMessage for all non-Slack platforms
# ---------------------------------------------------------------------------


class PlatformMessage(BaseMessage):
    """A BaseMessage implementation usable by Email, Mattermost, Telegram, etc.

    The dev-agents framework operates on BaseMessage instances. Slack has its
    own subclass inside the framework; this one covers every platform we add
    in this skill.
    """

    def __init__(
        self,
        *,
        user_name: str,
        user_id: str,
        content: str,
        date: datetime,
        thread_id: str = "",
        is_bot: bool = False,
        platform_name: str = "unknown",
        channel_id: str = "",
    ) -> None:
        self._user_name = user_name
        self._user_id = user_id
        self._content = content
        self._date = date if date.tzinfo else date.replace(tzinfo=UTC)
        self._thread_id = thread_id
        self._is_bot = is_bot
        self._platform_name = platform_name
        self._channel_id = channel_id

    # -- BaseMessage interface ------------------------------------------------

    def is_bot(self) -> bool:
        return self._is_bot

    def get_user_id(self) -> str:
        return self._user_id

    def get_user_name(self) -> str:
        return self._user_name

    def get_message_content(self) -> str:
        return self._content

    def get_message_date(self) -> datetime:
        return self._date

    def get_thread_id(self) -> str:
        return self._thread_id

    def get_formatted_message(self) -> str:
        ts = self._date.strftime("%Y-%m-%d %H:%M:%S")
        prefix = f"[{ts}] {self._user_name} ({self._platform_name})"
        return f"{prefix}: {self._content}"

    # -- Extra accessors used by platform services ----------------------------

    @property
    def content(self) -> str:
        return self._content

    @property
    def thread_id(self) -> str:
        return self._thread_id

    @property
    def channel_id(self) -> str:
        return self._channel_id

    @property
    def platform_name(self) -> str:
        return self._platform_name


# ---------------------------------------------------------------------------
# BasePlatformService — abstract base for all platform adapters
# ---------------------------------------------------------------------------


class BasePlatformService(ABC):
    """Lifecycle and messaging contract that every platform service implements.

    Subclasses must override ``connect``, ``disconnect``, ``send_response``,
    and ``update_response``.  The helper ``_dispatch_message`` routes an
    incoming ``PlatformMessage`` through the ClawAgent via the agent service.
    """

    # Platforms that support editing existing messages (like Slack) set this
    # to True so PlatformAgentContext can mirror status updates as edits.
    # Email and other fire-and-forget platforms leave it False.
    supports_updates: bool = False

    def __init__(self, name: str) -> None:
        self.name = name
        self._agent_service: Any = None
        self._task: asyncio.Task[None] | None = None
        self._running = False
        self.logger = get_logger(f"integrations.platforms.{name}")

    # -- Abstract interface ---------------------------------------------------

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the platform and start receiving messages.

        Returns ``True`` on success.
        """

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully disconnect from the platform."""

    @abstractmethod
    async def send_response(
        self,
        chat_id: str,
        thread_id: str,
        text: str,
    ) -> str | None:
        """Send a text response back to the platform.

        Returns the platform-specific message ID on success, or ``None`` on
        failure.  The returned ID can be passed to ``update_response`` later
        if the platform supports edits.
        """

    async def update_response(
        self,
        _chat_id: str,
        _message_id: str,
        _text: str,
    ) -> bool:
        """Edit an existing message in place.

        Default implementation returns ``False`` — platforms without edit
        support (email) rely on this fallback.  Telegram and Mattermost
        override this to perform an actual edit.
        """
        return False

    # -- Lifecycle helpers ----------------------------------------------------

    def set_agent_service(self, service: Any) -> None:
        """Inject the framework AgentService so messages can be dispatched."""
        self._agent_service = service

    async def start(self) -> None:
        """Start the service as a background asyncio task."""
        if self._running:
            self.logger.warning(f"{self.name}: already running")
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(), name=f"platform-{self.name}")
        self.logger.info(f"{self.name}: started")

    async def stop(self) -> None:
        """Stop the background task and disconnect."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        await self.disconnect()
        self.logger.info(f"{self.name}: stopped")

    async def _run_loop(self) -> None:
        """Connect and keep running; reconnect on transient failures."""
        backoff = 1.0
        max_backoff = 60.0
        while self._running:
            try:
                ok = await self.connect()
                if not ok:
                    self.logger.error(
                        f"{self.name}: connect() returned False, retrying in {backoff}s"
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, max_backoff)
                    continue
                backoff = 1.0
                # Subclass connect() should block until disconnected or error.
                # If it returns normally, we reconnect.
                self.logger.info(f"{self.name}: connect() returned, will reconnect")
            except asyncio.CancelledError:
                break
            except Exception:
                self.logger.exception(
                    f"{self.name}: error in run loop, retrying in {backoff}s"
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

    # -- Message dispatch -----------------------------------------------------

    async def _dispatch_message(self, message: PlatformMessage) -> None:
        """Route a PlatformMessage through the agent pipeline.

        Creates a PlatformAgentContext, populates it with the message, and
        invokes the agent via the framework's AgentService.
        """
        if self._agent_service is None:
            self.logger.error(f"{self.name}: agent_service not set, cannot dispatch")
            return

        chat_id = message.channel_id or message.get_user_id()
        thread_id = message.thread_id

        self.logger.info(
            f"{self.name}: dispatching message from {message.get_user_id()} "
            f"(chat={chat_id}, thread={thread_id})"
        )

        try:
            from integrations.platforms.agent_context import PlatformAgentContext

            context = PlatformAgentContext(
                platform_service=self,
                chat_id=chat_id,
                thread_id=thread_id,
                messages=[message],
            )

            from agents.agents.gitchatbot.agent import AGENT_NAME

            await self._agent_service.execute_agent_by_type(AGENT_NAME, context)
        except Exception:
            self.logger.exception(f"{self.name}: failed to dispatch message")

    # -- Utilities ------------------------------------------------------------

    @staticmethod
    def truncate_message(text: str, max_length: int = 4096) -> list[str]:
        """Split a long message into chunks respecting code block boundaries."""
        if len(text) <= max_length:
            return [text]

        chunks: list[str] = []
        while text:
            if len(text) <= max_length:
                chunks.append(text)
                break
            # Try to split at a newline near the limit
            cut = text.rfind("\n", 0, max_length)
            if cut <= 0:
                cut = max_length
            chunks.append(text[:cut])
            text = text[cut:].lstrip("\n")
        return chunks

    @staticmethod
    def get_authorized_ids(env_var: str) -> set[str] | None:
        """Parse a comma-separated list of IDs from an env var.

        Returns ``None`` when the env var is unset or empty (meaning all
        users are allowed).
        """
        raw = os.environ.get(env_var, "").strip()
        if not raw:
            return None
        return {uid.strip() for uid in raw.split(",") if uid.strip()}

    @staticmethod
    def env_flag(env_var: str, default: bool = False) -> bool:
        """Parse a boolean-ish env var.

        Truthy values: ``true``, ``1``, ``yes``, ``on`` (case-insensitive).
        Falsy values: ``false``, ``0``, ``no``, ``off``. An unset or empty
        var yields *default* silently; an unparseable value logs a warning
        and falls back to *default* so operators notice typos rather than
        silently getting the unintended default.
        """
        raw = os.environ.get(env_var)
        if raw is None or not raw.strip():
            return default
        value = raw.strip().lower()
        if value in ("true", "1", "yes", "on"):
            return True
        if value in ("false", "0", "no", "off"):
            return False
        logger.warning(
            "Unparseable boolean for %s=%r; falling back to default %s",
            env_var,
            raw,
            default,
        )
        return default
