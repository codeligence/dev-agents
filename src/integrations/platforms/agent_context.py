"""Platform implementation of AgentExecutionContext.

Provides a generic execution context for non-Slack platforms (Email,
Mattermost, Telegram).  Mirrors the structure of SlackAgentContext:

- On platforms that support edits (Telegram, Mattermost), status messages
  are posted once and then edited in place so the conversation is not
  spammed.
- On fire-and-forget platforms (Email), status updates are suppressed
  entirely — only the final response is delivered.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from core.config import BaseConfig, get_default_config
from core.log import get_logger
from core.message import BaseMessage, MessageList
from core.prompts import BasePrompts, get_default_prompts
from core.protocols.agent_protocols import AgentExecutionContext

if TYPE_CHECKING:
    from integrations.platforms.base import BasePlatformService

logger = get_logger("PlatformAgentContext")


class PlatformAgentContext(AgentExecutionContext):
    """Generic AgentExecutionContext for non-Slack platform services.

    Tracks the ID of the last status message so subsequent ``send_status``
    calls can edit it in place (mirroring ``SlackAgentContext``).  On
    platforms where ``supports_updates`` is ``False``, status messages are
    suppressed entirely and only the final response is sent.
    """

    def __init__(
        self,
        *,
        platform_service: BasePlatformService,
        chat_id: str,
        thread_id: str,
        messages: list[BaseMessage],
        config: BaseConfig | None = None,
        prompts: BasePrompts | None = None,
    ) -> None:
        self._platform_service = platform_service
        self._chat_id = chat_id
        self._thread_id = thread_id
        self._config = config or get_default_config()
        self._prompts = prompts or get_default_prompts()
        self._message_list = MessageList(messages)
        self.context_id = str(uuid.uuid4())
        self._last_message_id: str | None = None
        # Compact label used by info logs so each line carries the platform
        # name and a short context id — enough to correlate without leaking
        # message content.
        self._log_tag = f"{platform_service.name}/{self.context_id[:8]}"

        logger.info(
            f"Created platform agent context: platform={platform_service.name}, "
            f"chat={chat_id}, thread={thread_id}, context_id={self.context_id}"
        )

    # -- Internal helpers -----------------------------------------------------

    async def _send_or_update_message(self, text: str, is_status: bool) -> str | None:
        """Send a new message or update the last one (mirrors SlackAgentContext).

        Tries to edit ``_last_message_id`` first when the platform supports
        it; otherwise sends a new message.  Tracks the timestamp only for
        status messages so the final response either replaces it or starts
        fresh.
        """
        message_id: str | None = None

        if self._last_message_id and self._platform_service.supports_updates:
            updated = await self._platform_service.update_response(
                self._chat_id, self._last_message_id, text
            )
            if updated:
                message_id = self._last_message_id
            else:
                logger.warning(
                    f"Update failed for {self._last_message_id}, sending new message"
                )
                self._last_message_id = None
                message_id = await self._platform_service.send_response(
                    self._chat_id, self._thread_id, text
                )
        else:
            message_id = await self._platform_service.send_response(
                self._chat_id, self._thread_id, text
            )

        if is_status:
            self._last_message_id = message_id
        else:
            self._last_message_id = None

        return message_id

    # -- AgentExecutionContext interface --------------------------------------

    async def send_status(self, message: str) -> None:
        """Send a status update back to the platform.

        Skipped entirely on platforms that don't support edits, since
        emitting every status as a fresh message would spam the user.
        """
        if not self._platform_service.supports_updates:
            logger.debug(
                f"Skipping status on {self._platform_service.name} "
                f"(platform does not support message updates)"
            )
            return

        logger.info(
            "[%s] Sending status update (%d chars)", self._log_tag, len(message)
        )
        logger.debug("[%s] Status content: %s", self._log_tag, message)
        await self._send_or_update_message(message, is_status=True)

    async def send_response(self, response: str) -> None:
        """Send the final agent response back to the platform."""
        logger.info("[%s] Sending response (%d chars)", self._log_tag, len(response))
        logger.debug("[%s] Response content: %s", self._log_tag, response)
        await self._send_or_update_message(response, is_status=False)

    async def send_attachment(
        self, name: str, content: str | bytes, is_binary: bool = False
    ) -> None:
        """Send an attachment as a text message (platforms don't support rich attachments yet)."""
        if is_binary:
            raise NotImplementedError(
                "Binary attachments not supported on this platform"
            )
        text = (
            content
            if isinstance(content, str)
            else content.decode("utf-8", errors="replace")
        )
        header = f"**{name}**\n\n"
        await self._send_or_update_message(header + text, is_status=False)

    async def download_attachment(self, attachment_id: str) -> str:
        """Attachment downloads not supported by generic platform contexts."""
        raise NotImplementedError("Attachment downloads not supported on this platform")

    def get_message_list(self) -> MessageList:
        """Get the list of messages available to the agent."""
        return self._message_list

    def get_config(self) -> BaseConfig:
        """Get the configuration object."""
        return self._config

    def get_prompts(self) -> BasePrompts:
        """Get the prompts object."""
        return self._prompts

    def get_execution_id(self) -> str:
        """Get the unique execution identifier."""
        return self._thread_id or self._chat_id

    def get_context_id(self) -> str:
        """Get the unique context identifier."""
        return self.context_id
