"""Telegram platform service for dev-agents-claw.

Uses python-telegram-bot for polling-based message reception and sending.
Ported from hermes-agent/gateway/platforms/telegram.py (MIT).

Core features ported:
- Long-polling with conflict detection (409) and network error reconnection
- MarkdownV2 formatting with plain-text fallback
- Mention-gating in groups (require @mention or reply-to-bot)
- Authorization via TELEGRAM_ALLOWED_USERS

Deferred (not ported):
- Media batching, DM topics, webhook mode, fallback transport, sticker analysis

Environment variables:
    TELEGRAM_BOT_TOKEN              — Bot token from @BotFather
    TELEGRAM_REQUIRE_MENTION        — Require @mention in groups (default: false)
    TELEGRAM_FREE_RESPONSE_CHATS    — Chat IDs where bot responds without mention
    TELEGRAM_ALLOWED_USERS          — Comma-separated allowed user IDs (optional)

Dependencies: python-telegram-bot>=22.6,<23
"""

from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from integrations.platforms.base import BasePlatformService, PlatformMessage

try:
    from telegram import Update, Bot, Message
    from telegram.ext import (
        Application,
        MessageHandler as TelegramMessageHandler,
        ContextTypes,
        filters,
    )
    from telegram.constants import ParseMode, ChatType
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

# MarkdownV2 escape pattern
_MDV2_ESCAPE_RE = re.compile(r'([_*\[\]()~`>#\+\-=|{}.!\\])')

# Telegram message length limit
MAX_MESSAGE_LENGTH = 4096


def _escape_mdv2(text: str) -> str:
    """Escape Telegram MarkdownV2 special characters."""
    return _MDV2_ESCAPE_RE.sub(r'\\\1', text)


def _strip_mdv2(text: str) -> str:
    """Strip MarkdownV2 escape backslashes to produce clean plain text."""
    cleaned = re.sub(r'\\([_*\[\]()~`>#\+\-=|{}.!\\])', r'\1', text)
    cleaned = re.sub(r'\*([^*]+)\*', r'\1', cleaned)
    cleaned = re.sub(r'(?<!\w)_([^_]+)_(?!\w)', r'\1', cleaned)
    cleaned = re.sub(r'~([^~]+)~', r'\1', cleaned)
    cleaned = re.sub(r'\|\|([^|]+)\|\|', r'\1', cleaned)
    return cleaned


def _format_mdv2(content: str) -> str:
    """Convert standard markdown to Telegram MarkdownV2 format.

    Protects code blocks/spans, converts headers/bold/italic/links,
    then escapes remaining special characters.
    """
    if not content:
        return content

    placeholders: dict = {}
    counter = [0]

    def _ph(value: str) -> str:
        key = f"\x00PH{counter[0]}\x00"
        counter[0] += 1
        placeholders[key] = value
        return key

    text = content

    # Protect fenced code blocks
    def _protect_fenced(m: re.Match) -> str:
        raw = m.group(0)
        open_end = raw.index('\n') + 1 if '\n' in raw[3:] else 3
        opening = raw[:open_end]
        body = raw[open_end:-3]
        body = body.replace('\\', '\\\\').replace('`', '\\`')
        return _ph(opening + body + '```')

    text = re.sub(r'(```(?:[^\n]*\n)?[\s\S]*?```)', _protect_fenced, text)

    # Protect inline code
    text = re.sub(
        r'(`[^`]+`)',
        lambda m: _ph(m.group(0).replace('\\', '\\\\')),
        text,
    )

    # Convert markdown links
    def _convert_link(m: re.Match) -> str:
        display = _escape_mdv2(m.group(1))
        url = m.group(2).replace('\\', '\\\\').replace(')', '\\)')
        return _ph(f'[{display}]({url})')

    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', _convert_link, text)

    # Headers -> bold
    def _convert_header(m: re.Match) -> str:
        inner = m.group(1).strip()
        inner = re.sub(r'\*\*(.+?)\*\*', r'\1', inner)
        return _ph(f'*{_escape_mdv2(inner)}*')

    text = re.sub(r'^#{1,6}\s+(.+)$', _convert_header, text, flags=re.MULTILINE)

    # Bold **text** -> *text*
    text = re.sub(
        r'\*\*(.+?)\*\*',
        lambda m: _ph(f'*{_escape_mdv2(m.group(1))}*'),
        text,
    )

    # Italic *text* -> _text_
    text = re.sub(
        r'\*([^*\n]+)\*',
        lambda m: _ph(f'_{_escape_mdv2(m.group(1))}_'),
        text,
    )

    # Strikethrough ~~text~~ -> ~text~
    text = re.sub(
        r'~~(.+?)~~',
        lambda m: _ph(f'~{_escape_mdv2(m.group(1))}~'),
        text,
    )

    # Blockquotes
    text = re.sub(
        r'^(>{1,3}) (.+)$',
        lambda m: _ph(m.group(1) + ' ' + _escape_mdv2(m.group(2))),
        text,
        flags=re.MULTILINE,
    )

    # Escape remaining special characters
    text = _escape_mdv2(text)

    # Restore placeholders in reverse order
    for key in reversed(list(placeholders.keys())):
        text = text.replace(key, placeholders[key])

    return text


class TelegramService(BasePlatformService):
    """Telegram bot service using long-polling."""

    supports_updates = True

    def __init__(self) -> None:
        super().__init__("telegram")

        self._token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self._allowed_users = self.get_authorized_ids("TELEGRAM_ALLOWED_USERS")

        self._app: Any = None  # telegram.ext.Application
        self._bot: Any = None  # telegram.Bot
        self._bot_username: str = ""
        self._bot_id: int = 0
        self._polling_conflict_count: int = 0
        self._polling_network_error_count: int = 0
        self._polling_error_callback_ref: Any = None
        self._polling_error_task: Any = None

    # -- BasePlatformService interface ----------------------------------------

    async def connect(self) -> bool:
        """Build the Application, register handlers, and start polling (blocks)."""
        if not TELEGRAM_AVAILABLE:
            self.logger.error(
                "python-telegram-bot not installed. Run: pip install 'python-telegram-bot>=22.6,<23'"
            )
            return False

        if not self._token:
            self.logger.error("TELEGRAM_BOT_TOKEN not set")
            return False

        try:
            self._app = Application.builder().token(self._token).build()
            self._bot = self._app.bot

            # Register handlers
            self._app.add_handler(TelegramMessageHandler(
                filters.TEXT & ~filters.COMMAND, self._handle_text_message,
            ))
            self._app.add_handler(TelegramMessageHandler(
                filters.COMMAND, self._handle_command,
            ))

            # Initialize with retry for transient TLS errors
            try:
                from telegram.error import NetworkError, TimedOut
            except ImportError:
                NetworkError = TimedOut = OSError

            for attempt in range(3):
                try:
                    await self._app.initialize()
                    break
                except (NetworkError, TimedOut, OSError) as e:
                    if attempt < 2:
                        wait = 2 ** attempt
                        self.logger.warning(
                            "Connect attempt %d/3 failed: %s — retrying in %ds",
                            attempt + 1, e, wait,
                        )
                        await asyncio.sleep(wait)
                    else:
                        raise

            await self._app.start()

            # Cache bot identity for mention-gating
            me = await self._bot.get_me()
            self._bot_username = me.username or ""
            self._bot_id = me.id
            self.logger.info(
                "Connected as @%s (%s)", self._bot_username, self._bot_id,
            )

            # Start polling with error callback
            loop = asyncio.get_running_loop()

            def _polling_error_callback(error: Exception) -> None:
                if self._polling_error_task and not self._polling_error_task.done():
                    return
                if self._looks_like_polling_conflict(error):
                    self._polling_error_task = loop.create_task(
                        self._handle_polling_conflict(error)
                    )
                elif self._looks_like_network_error(error):
                    self.logger.warning("Network error, scheduling reconnect: %s", error)
                    self._polling_error_task = loop.create_task(
                        self._handle_polling_network_error(error)
                    )
                else:
                    self.logger.error("Polling error: %s", error)

            self._polling_error_callback_ref = _polling_error_callback

            await self._app.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
                error_callback=_polling_error_callback,
            )

            # Block until cancelled
            try:
                while True:
                    await asyncio.sleep(3600)
            except asyncio.CancelledError:
                pass

            return True

        except Exception as e:
            self.logger.error("Failed to connect: %s", e, exc_info=True)
            return False

    async def disconnect(self) -> None:
        if self._app:
            try:
                if self._app.updater and self._app.updater.running:
                    await self._app.updater.stop()
                if self._app.running:
                    await self._app.stop()
                await self._app.shutdown()
            except Exception as e:
                self.logger.warning("Error during disconnect: %s", e)
        self._app = None
        self._bot = None

    async def send_response(
        self, chat_id: str, thread_id: str, text: str
    ) -> Optional[str]:
        """Send a message to a Telegram chat with MarkdownV2, falling back to plain text.

        Returns the message ID of the last sent chunk on success so the
        context can edit it later for status updates.  Returns ``None`` on
        failure.
        """
        if not self._bot or not text or not text.strip():
            return None

        formatted = _format_mdv2(text)
        chunks = self.truncate_message(formatted, MAX_MESSAGE_LENGTH)

        # Escape chunk indicators for MarkdownV2
        if len(chunks) > 1:
            chunks = [
                re.sub(r" \((\d+)/(\d+)\)$", r" \\(\1/\2\\)", chunk)
                for chunk in chunks
            ]

        try:
            from telegram.error import NetworkError as _NetErr, BadRequest as _BadReq
        except ImportError:
            _NetErr = OSError
            _BadReq = None

        last_message_id: Optional[str] = None

        for chunk in chunks:
            for attempt in range(3):
                try:
                    sent: Any = None
                    try:
                        sent = await self._bot.send_message(
                            chat_id=int(chat_id),
                            text=chunk,
                            parse_mode=ParseMode.MARKDOWN_V2,
                            message_thread_id=int(thread_id) if thread_id else None,
                        )
                    except Exception as md_err:
                        if "parse" in str(md_err).lower() or "markdown" in str(md_err).lower():
                            self.logger.warning("MarkdownV2 failed, falling back to plain: %s", md_err)
                            sent = await self._bot.send_message(
                                chat_id=int(chat_id),
                                text=_strip_mdv2(chunk),
                                parse_mode=None,
                                message_thread_id=int(thread_id) if thread_id else None,
                            )
                        else:
                            raise
                    if sent is not None:
                        last_message_id = str(sent.message_id)
                    break
                except Exception as send_err:
                    if _BadReq and isinstance(send_err, _BadReq):
                        err_lower = str(send_err).lower()
                        if "thread not found" in err_lower and thread_id:
                            thread_id = ""
                            continue
                        raise
                    if isinstance(send_err, (_NetErr, OSError)) and attempt < 2:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    self.logger.error("Send failed to %s: %s", chat_id, send_err)
                    return None

        return last_message_id

    async def update_response(
        self, chat_id: str, message_id: str, text: str
    ) -> bool:
        """Edit a previously-sent Telegram message in place.

        Returns ``False`` if the new text exceeds the per-message limit
        (Telegram rejects oversized edits) or the edit API call fails —
        the caller then falls back to sending a fresh message.
        """
        if not self._bot or not text or not text.strip():
            return False

        formatted = _format_mdv2(text)
        if len(formatted) > MAX_MESSAGE_LENGTH:
            return False

        try:
            from telegram.error import BadRequest as _BadReq
        except ImportError:
            _BadReq = None

        try:
            try:
                await self._bot.edit_message_text(
                    chat_id=int(chat_id),
                    message_id=int(message_id),
                    text=formatted,
                    parse_mode=ParseMode.MARKDOWN_V2,
                )
            except Exception as md_err:
                if "parse" in str(md_err).lower() or "markdown" in str(md_err).lower():
                    await self._bot.edit_message_text(
                        chat_id=int(chat_id),
                        message_id=int(message_id),
                        text=_strip_mdv2(formatted),
                        parse_mode=None,
                    )
                else:
                    raise
            return True
        except Exception as edit_err:
            # "message is not modified" means the new text matches the old —
            # treat as success so the caller doesn't send a duplicate.
            if _BadReq and isinstance(edit_err, _BadReq):
                if "message is not modified" in str(edit_err).lower():
                    return True
            self.logger.warning("Edit failed for message %s: %s", message_id, edit_err)
            return False

    # -- Polling error handlers -----------------------------------------------

    @staticmethod
    def _looks_like_polling_conflict(error: Exception) -> bool:
        text = str(error).lower()
        return (
            error.__class__.__name__.lower() == "conflict"
            or "terminated by other getupdates request" in text
            or "another bot instance is running" in text
        )

    @staticmethod
    def _looks_like_network_error(error: Exception) -> bool:
        name = error.__class__.__name__.lower()
        if name in ("networkerror", "timedout", "connectionerror"):
            return True
        try:
            from telegram.error import NetworkError, TimedOut
            if isinstance(error, (NetworkError, TimedOut)):
                return True
        except ImportError:
            pass
        return isinstance(error, OSError)

    async def _handle_polling_conflict(self, error: Exception) -> None:
        """Retry polling after a 409 conflict (another instance using same token)."""
        MAX_RETRIES = 3
        RETRY_DELAY = 10

        self._polling_conflict_count += 1
        if self._polling_conflict_count <= MAX_RETRIES:
            self.logger.warning(
                "Polling conflict (%d/%d), retrying in %ds: %s",
                self._polling_conflict_count, MAX_RETRIES, RETRY_DELAY, error,
            )
            try:
                if self._app and self._app.updater and self._app.updater.running:
                    await self._app.updater.stop()
            except Exception:
                pass
            await asyncio.sleep(RETRY_DELAY)
            try:
                await self._app.updater.start_polling(
                    allowed_updates=Update.ALL_TYPES,
                    drop_pending_updates=False,
                    error_callback=self._polling_error_callback_ref,
                )
                self._polling_conflict_count = 0
            except Exception as e:
                self.logger.warning("Polling retry failed: %s", e)
        else:
            self.logger.error(
                "Polling conflict persists after %d retries. "
                "Ensure only one bot instance uses this token.", MAX_RETRIES,
            )

    async def _handle_polling_network_error(self, error: Exception) -> None:
        """Reconnect polling after transient network errors with exponential backoff."""
        MAX_RETRIES = 10
        BASE_DELAY = 5
        MAX_DELAY = 60

        self._polling_network_error_count += 1
        attempt = self._polling_network_error_count

        if attempt > MAX_RETRIES:
            self.logger.error(
                "Could not reconnect after %d network error retries: %s",
                MAX_RETRIES, error,
            )
            return

        delay = min(BASE_DELAY * (2 ** (attempt - 1)), MAX_DELAY)
        self.logger.warning(
            "Network error (attempt %d/%d), reconnecting in %ds: %s",
            attempt, MAX_RETRIES, delay, error,
        )
        await asyncio.sleep(delay)

        try:
            if self._app and self._app.updater and self._app.updater.running:
                await self._app.updater.stop()
        except Exception:
            pass

        try:
            await self._app.updater.start_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=False,
                error_callback=self._polling_error_callback_ref,
            )
            self.logger.info("Polling resumed after network error (attempt %d)", attempt)
            self._polling_network_error_count = 0
        except Exception as e:
            self.logger.warning("Polling reconnect failed: %s", e)
            asyncio.ensure_future(self._handle_polling_network_error(e))

    # -- Message handlers -----------------------------------------------------

    async def _handle_text_message(self, update: "Update", context: Any) -> None:
        """Handle incoming text messages."""
        if not update.message or not update.message.text:
            return
        if not self._should_process_message(update.message):
            return

        msg = update.message
        text = self._clean_bot_mention(msg.text)
        await self._dispatch_telegram_message(msg, text)

    async def _handle_command(self, update: "Update", context: Any) -> None:
        """Handle incoming /command messages."""
        if not update.message or not update.message.text:
            return
        if not self._should_process_message(update.message, is_command=True):
            return

        msg = update.message
        await self._dispatch_telegram_message(msg, msg.text)

    async def _dispatch_telegram_message(self, msg: Any, text: str) -> None:
        """Convert a Telegram message to PlatformMessage and dispatch."""
        user = msg.from_user
        chat = msg.chat

        user_id = str(user.id) if user else "unknown"
        user_name = user.full_name if user else "unknown"

        # Authorization check
        if self._allowed_users is not None and user_id not in self._allowed_users:
            self.logger.info("Ignoring message from unauthorized user: %s", user_id)
            return

        thread_id = str(msg.message_thread_id) if msg.message_thread_id else ""

        message = PlatformMessage(
            user_name=user_name,
            user_id=user_id,
            content=text,
            date=msg.date if msg.date else datetime.now(timezone.utc),
            thread_id=thread_id,
            channel_id=str(chat.id),
            platform_name="telegram",
        )

        self.logger.info(
            "New message from %s in %s: %s",
            user_name, chat.id, text[:80],
        )
        await self._dispatch_message(message)

    # -- Mention-gating -------------------------------------------------------

    def _should_process_message(self, message: Any, *, is_command: bool = False) -> bool:
        """Apply group mention-gating rules. DMs are always processed."""
        chat_type = str(getattr(getattr(message, "chat", None), "type", "")).split(".")[-1].lower()
        if chat_type not in ("group", "supergroup"):
            return True

        chat_id = str(getattr(getattr(message, "chat", None), "id", ""))

        # Free-response chats bypass mention requirement
        free_raw = os.getenv("TELEGRAM_FREE_RESPONSE_CHATS", "")
        free_chats = {c.strip() for c in free_raw.split(",") if c.strip()}
        if chat_id in free_chats:
            return True

        require_mention = os.getenv(
            "TELEGRAM_REQUIRE_MENTION", "false",
        ).lower() in ("true", "1", "yes", "on")

        if not require_mention:
            return True
        if is_command:
            return True

        # Check if replying to bot
        reply = getattr(message, "reply_to_message", None)
        if reply:
            reply_user = getattr(reply, "from_user", None)
            if reply_user and getattr(reply_user, "id", None) == self._bot_id:
                return True

        # Check for @mention
        text = getattr(message, "text", "") or getattr(message, "caption", "") or ""
        if self._bot_username and f"@{self._bot_username}".lower() in text.lower():
            return True

        return False

    def _clean_bot_mention(self, text: str | None) -> str:
        """Strip @bot_username from message text."""
        if not text or not self._bot_username:
            return text or ""
        return re.sub(
            rf"(?i)@{re.escape(self._bot_username)}\b[,:\-]*\s*", "", text,
        ).strip() or text
