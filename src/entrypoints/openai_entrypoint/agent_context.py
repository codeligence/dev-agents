"""OpenAI-compatible implementation of AgentExecutionContext.

Collects agent responses and status updates. For streaming mode, pushes
response chunks to an async queue. For non-streaming, buffers the full response.
"""

from typing import Any
import asyncio
import uuid

from core.config import BaseConfig
from core.log import get_logger
from core.message import MessageList
from core.prompts import BasePrompts
from core.protocols.agent_protocols import AgentExecutionContext

logger = get_logger("OpenAIAgentContext")


class OpenAIAgentContext(AgentExecutionContext):
    """AgentExecutionContext that collects responses for OpenAI-format output.

    In streaming mode, each send_response() and send_status() pushes to a queue
    consumed by the SSE generator. In non-streaming mode, responses are buffered
    and returned at the end.
    """

    def __init__(
        self,
        message_list: MessageList,
        config: BaseConfig,
        prompts: BasePrompts,
        thread_id: str = "default",
        streaming: bool = False,
        event_queue: asyncio.Queue[Any] | None = None,
    ) -> None:
        self.message_list = message_list
        self.config = config
        self.prompts = prompts
        self.thread_id = thread_id
        self.context_id = str(uuid.uuid4())
        self.streaming = streaming

        # Queue for streaming mode — carries response text chunks
        self.event_queue: asyncio.Queue[Any] = event_queue or asyncio.Queue()

        # Buffer for non-streaming mode
        self._response_parts: list[str] = []

        logger.info(
            f"Created OpenAI agent context: thread_id={thread_id}, streaming={streaming}"
        )

    async def send_status(self, message: str) -> None:
        """Send status update. In streaming mode, emits a keepalive-style event."""
        logger.info(f"Status: {message}")
        if self.streaming:
            # Push a status marker so the generator knows agent is alive
            await self.event_queue.put({"type": "status", "message": message})

    async def send_response(self, response: str) -> None:
        """Send agent response.

        Streaming: pushes response text as a chunk to the queue.
        Non-streaming: appends to internal buffer.
        """
        logger.info(f"Response: {response[:100]}...")
        if self.streaming:
            await self.event_queue.put({"type": "content", "text": response})
        else:
            self._response_parts.append(response)

    async def send_attachment(
        self, name: str, content: str | bytes, is_binary: bool = False
    ) -> None:
        """Attachments not supported in OpenAI-compatible mode — ignored."""
        size = len(content) if content is not None else 0
        logger.info(
            f"Attachment '{name}' ignored in OpenAI mode "
            f"(size={size}, binary={is_binary})"
        )

    async def download_attachment(self, attachment_id: str) -> str:
        """Attachment downloads not supported in OpenAI-compatible mode."""
        raise NotImplementedError("Attachment downloads not supported in OpenAI mode")

    def get_full_response(self) -> str:
        """Get buffered response (non-streaming mode)."""
        return "\n\n".join(self._response_parts)

    # ── Protocol methods ────────────────────────────────────────────────

    def get_message_list(self) -> MessageList:
        return self.message_list

    def get_config(self) -> BaseConfig:
        return self.config

    def get_prompts(self) -> BasePrompts:
        return self.prompts

    def get_context_id(self) -> str:
        return self.context_id

    def get_execution_id(self) -> str:
        return self.thread_id
