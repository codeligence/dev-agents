"""Slack implementation of AgentExecutionContext."""

from typing import Any
import contextlib
import uuid

from core.agents.models import ToolRegistration
from core.config import BaseConfig
from core.log import get_logger
from core.message import MessageList
from core.prompts import BasePrompts
from core.protocols.agent_protocols import AgentExecutionContext
from integrations.slack.models import SlackBotConfig
from integrations.slack.slack_client_service import SlackClientService

logger = get_logger("SlackAgentContext")


class SlackAgentContext(AgentExecutionContext):
    """Slack-specific implementation of AgentExecutionContext.

    Provides Slack-specific message reporting and thread management
    while implementing the standard agent execution interface.
    """

    def __init__(
        self,
        slack_client: SlackClientService,
        channel_id: str,
        thread_ts: str | None,
        message_list: MessageList,
        config: BaseConfig,
        prompts: BasePrompts,
    ):
        self.slack_client = slack_client
        self.channel_id = channel_id
        self.thread_ts = thread_ts
        self.message_list = message_list
        self.config = config
        self.prompts = prompts
        self.context_id = str(uuid.uuid4())
        self.last_message_ts: str | None = None
        self._include_feedback = SlackBotConfig(config).get_include_feedback_buttons()

        # Check if bot is mentioned in the last message
        self._bot_mentioned = False
        if message_list and len(message_list) > 0:
            messages = message_list.get_messages()
            if messages:
                last_message = messages[-1]
                self._bot_mentioned = slack_client.is_bot_mentioned(
                    last_message.get_message_content()
                )

        logger.info(
            f"Created Slack agent context: channel={channel_id}, thread={thread_ts}, context_id={self.context_id}, bot_mentioned={self._bot_mentioned}"
        )

    async def _send_or_update_message(
        self, text: str, is_status: bool = False
    ) -> str | None:
        """Send a new message or update the last one.

        Tries to update an existing message first.  If the update fails,
        falls back to sending a new message.

        Args:
            text: Message text to send
            is_status: If True, stores timestamp for future updates;
                      if False, clears it (final response)

        Returns:
            Message timestamp if successful, None otherwise
        """
        thread = self.thread_ts or self.channel_id
        message_ts: str | None = None

        try:
            include_feedback = self._include_feedback and not is_status
            if self.last_message_ts:
                # Try updating the existing message
                message_ts = await self.slack_client.update_message(
                    channel_id=self.channel_id,
                    message_ts=self.last_message_ts,
                    text=text,
                    thread_ts=thread,
                    include_feedback=include_feedback,
                )
                if not message_ts:
                    # Update failed — fall back to new message
                    logger.warning(
                        f"Update failed for {self.last_message_ts}, sending new message"
                    )
                    self.last_message_ts = None
                    message_ts = await self.slack_client.send_reply(
                        channel_id=self.channel_id,
                        thread_ts=thread,
                        text=text,
                        include_feedback=include_feedback,
                    )
            else:
                message_ts = await self.slack_client.send_reply(
                    channel_id=self.channel_id,
                    thread_ts=thread,
                    text=text,
                    include_feedback=include_feedback,
                )

            if message_ts:
                self.last_message_ts = message_ts if is_status else None

            return message_ts

        except Exception as e:
            logger.error(f"Failed to send/update message: {e}")
            return None

    async def send_status(self, message: str) -> None:
        """Send agent execution status to Slack.

        Posts a status message to the Slack channel/thread.

        Args:
            message: Status message to send
        """
        logger.info(f"Sending status: {message}")

        # Format status message with emoji for better UX
        formatted_message = f"{message}"

        # Send or update message - timestamp management handled by shared method
        await self._send_or_update_message(formatted_message, is_status=True)

    async def send_response(self, response: str) -> None:
        """Send final response to Slack.

        Posts the agent's final response to the Slack channel/thread.

        Args:
            response: Final response message
        """
        logger.info(f"Sending response: {response[:100]}...")

        # Send or update message - timestamp cleared automatically by shared method
        message_ts = await self._send_or_update_message(response, is_status=False)

        if not message_ts:
            logger.error("Failed to send response to Slack — all attempts exhausted")
            with contextlib.suppress(Exception):
                await self._send_or_update_message(
                    "❌ Sorry, I encountered an error while sending my response.",
                    is_status=False,
                )
            raise Exception("Failed to send response to Slack: message_ts is None")

    async def send_attachment(
        self, name: str, content: str | bytes, is_binary: bool = False
    ) -> None:
        """Post an attachment to Slack.

        For text content: Creates a Slack canvas with the content
        For binary content: Raises NotImplementedError (not yet supported)

        Args:
            name: Title/name of the attachment
            content: Content of the attachment (text/markdown or binary)
            is_binary: Whether the content is binary data (default False)

        Raises:
            NotImplementedError: If binary attachments are requested
        """
        logger.info(f"Posting attachment: {name} (binary: {is_binary})")

        if is_binary:
            logger.error("Binary attachments not yet supported in Slack")
            raise NotImplementedError("Binary attachments not yet supported in Slack")

        try:
            # For text content, create a Slack canvas
            content_str = (
                content
                if isinstance(content, str)
                else content.decode("utf-8", errors="replace")
            )

            canvas_id = await self.slack_client.post_canvas(
                channel_id=self.channel_id,
                title=name,
                markdown_content=content_str,
                thread_ts=self.thread_ts,
                include_feedback=self._include_feedback,
            )

            if canvas_id:
                logger.info(
                    f"Successfully posted attachment '{name}' as canvas: {canvas_id}"
                )
            else:
                logger.error(
                    f"Failed to post attachment '{name}' - canvas creation failed"
                )
                raise Exception(f"Failed to create canvas for attachment '{name}'")

        except Exception as e:
            logger.error(f"Error posting attachment '{name}': {str(e)}")
            raise Exception(f"Failed to post attachment '{name}': {str(e)}")

    async def download_attachment(self, attachment_id: str) -> str:
        """Download a Slack file attachment by ID.

        Downloads the file to {storage_dir}/attachments/ directory,
        using the project's configured storage instance.

        Args:
            attachment_id: Slack file ID from [#attachment] marker

        Returns:
            Local file path where the attachment was saved

        Raises:
            RuntimeError: If the download fails
        """
        from core.storage import FileStorage, get_storage

        storage = get_storage(self.config)
        if not isinstance(storage, FileStorage):
            raise RuntimeError("Attachment downloads require FileStorage backend")
        target_dir = storage.storage_dir / "attachments"
        result = await self.slack_client.download_file(attachment_id, target_dir)
        if result is None:
            raise RuntimeError(f"Failed to download attachment {attachment_id}")
        logger.info(f"Downloaded attachment {attachment_id} to {result}")
        return str(result)

    @staticmethod
    def get_download_attachment_tool() -> ToolRegistration:
        """Return a ToolRegistration for downloading Slack file attachments.

        The returned registration can be hooked into agent tool registration
        by the application. It is not automatically activated.

        Returns:
            ToolRegistration for the download_attachment tool
        """
        from pydantic_ai import RunContext

        from core.skills.context import SkillContext

        async def download_attachment(ctx: RunContext[Any], attachment_id: str) -> str:
            """Download a file attachment by its ID and return the local path.

            Use this when a message contains [#attachment id=... name=...] markers.
            Downloads the file to local storage so you can read or process it.

            Args:
                attachment_id: The attachment ID from the [#attachment] marker

            Returns:
                Local file path where the attachment was saved
            """
            sc = SkillContext(ctx)
            await sc.send_toolcall_message("Downloading attachment...")
            return await sc.download_attachment(attachment_id)

        return ToolRegistration(
            name="download_attachment",
            description=(
                "Download a file attachment by its ID. Use when a message "
                "contains [#attachment id=... name=...] markers. Returns "
                "the local file path so you can read or process the file. "
                "Args: attachment_id (the ID from the attachment marker)."
            ),
            function=download_attachment,
            priority=25,
        )

    def get_message_list(self) -> MessageList:
        """Get the list of messages available to the agent.

        Returns:
            MessageList containing available messages
        """
        return self.message_list

    def get_config(self) -> BaseConfig:
        """Get the configuration object.

        Returns:
            BaseConfig instance for accessing configuration
        """
        return self.config

    def get_prompts(self) -> BasePrompts:
        """Get the prompts object.

        Returns:
            BasePrompts instance for accessing prompts
        """
        return self.prompts

    def get_context_id(self) -> str:
        """Get the unique context identifier.

        Returns:
            Unique identifier for this execution context
        """
        return self.context_id

    def get_execution_id(self) -> str:
        """Get the unique execution identifier for this agent context.

        Uses thread_ts as the primary identifier for state persistence.
        Falls back to channel_id if no thread exists.

        Returns:
            Unique identifier that can be used for state persistence
        """
        return self.thread_ts or self.channel_id

    def get_slack_info(self) -> dict[str, Any]:
        """Get Slack-specific context information.

        Returns:
            Dictionary containing Slack channel and thread information
        """
        return {
            "channel_id": self.channel_id,
            "thread_ts": self.thread_ts,
            "context_id": self.context_id,
        }

    def get_origin_info(self) -> dict[str, Any]:
        """Serialize Slack context for deferred recreation.

        Returns:
            Dict with Slack-specific fields needed to recreate this context.
        """
        return {
            "type": "slack",
            "channel_id": self.channel_id,
            "thread_ts": self.thread_ts,
        }

    def is_bot_mentioned(self) -> bool:
        """Check if the bot was mentioned in the last message.

        Returns:
            True if the bot was mentioned in the last message, False otherwise
        """
        return self._bot_mentioned


class ScheduledSlackContext(SlackAgentContext):
    """SlackAgentContext variant for scheduled (deferred) execution.

    Status updates are silenced to avoid Slack spam; only the final
    response and attachments are posted.
    """

    async def send_status(self, message: str) -> None:
        logger.debug(f"[scheduled] status silenced: {message[:200]}")


def register_slack_origin_factory(slack_client: SlackClientService) -> None:
    """Register the Slack origin context factory.

    Should be called once during Slack entrypoint startup so that deferred
    execution paths (e.g. the scheduler skill) can recreate Slack contexts.

    Args:
        slack_client: A connected SlackClientService for posting messages.
    """
    from core.context_factory import register_origin_factory

    def _factory(
        origin_info: dict[str, Any],
        config: BaseConfig,
        prompts: BasePrompts,
    ) -> ScheduledSlackContext:
        return ScheduledSlackContext(
            slack_client=slack_client,
            channel_id=origin_info["channel_id"],
            thread_ts=origin_info.get("thread_ts"),
            message_list=MessageList([]),
            config=config,
            prompts=prompts,
        )

    register_origin_factory("slack", _factory)
