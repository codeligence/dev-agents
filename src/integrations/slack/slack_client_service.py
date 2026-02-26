from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC
from typing import Any, cast
import threading

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.client import BaseSocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse

from core.log import get_logger
from integrations.slack.models import SlackBotConfig
from integrations.slack.thread_participant_tracker import ThreadParticipantTracker


@dataclass
class ThreadReplyDecision:
    """Result of thread reply processing decision."""

    should_process: bool
    conversation: list[dict[str, Any]] | None = None


class SlackClientService:
    def __init__(
        self,
        slack_config: SlackBotConfig,
        max_connection_failures: int = 5,
    ):
        # Setup logging using centralized log file path utility
        self.log = get_logger(logger_name="SlackClientService", level="INFO")
        # Logging configuration is now DRY and managed in one place via get_log_file_path.
        self.user_info_cache: dict[str, dict[str, Any]] = {}  # Cache for user info

        # Load Slack tokens from config
        if not slack_config:
            raise ValueError("SlackClientService requires slack_config parameter")

        self.bot_token = slack_config.get_bot_token()
        app_token = slack_config.get_app_token()

        self.client = WebClient(token=self.bot_token)
        self.user_info_cache = {}

        # Message callback for real-time processing
        self.message_callback: Callable[[dict[str, Any]], None] | None = None

        # Connection failure tracking for graceful shutdown
        self._max_connection_failures = max_connection_failures
        self._consecutive_failures = 0
        self._failure_lock = threading.Lock()
        self._shutdown_callback: Callable[[], None] | None = None

        # Initialize Socket Mode client
        self.socket_client = SocketModeClient(
            app_token=app_token, web_client=self.client
        )

        # Register error listener for connection failure tracking
        self.socket_client.on_error_listeners.append(self._handle_socket_error)

        self.socket_client.socket_mode_request_listeners.append(
            self._socket_event_handler
        )

        # try to getting the ID bot
        self.bot_id: str | None = None
        self.bot_mention: str | None = None
        try:
            bot_info = self.client.auth_test()
            self.bot_id = bot_info["user_id"]
            self.bot_mention = f"<@{self.bot_id}>"
            self.log.info(
                f"Bot ID: {self.bot_id}, mention: {self.bot_mention}, name: {bot_info['user']}"
            )
        except SlackApiError as e:
            self.log.error(f"Error fetching bot info: {e.response['error']}")
            self.bot_id = None
            self.bot_mention = None

        # Initialize participant tracker for thread filtering
        self._participant_tracker = (
            ThreadParticipantTracker(bot_id=self.bot_id) if self.bot_id else None
        )

    def get_user_real_name(self, user_id: str) -> str:
        if user_id in self.user_info_cache:
            user_info = self.user_info_cache[user_id]
        else:
            response = self.client.users_info(user=user_id)
            # Handle SlackResponse or dict response
            if hasattr(response, "data") and isinstance(response.data, dict):
                user_info = response.data
            elif isinstance(response, dict):
                user_info = response
            else:
                user_info = {}
            self.user_info_cache[user_id] = user_info
        real_name = user_info.get("user", {}).get("real_name", "unknown")
        return str(real_name) if real_name is not None else "unknown"

    def get_thread_conversation(
        self, channel_id: str, thread_ts: str
    ) -> list[dict[str, Any]]:
        """Get all messages in a thread conversation.

        Args:
            channel_id: The channel ID containing the thread
            thread_ts: The timestamp of the thread

        Returns:
            List of message dictionaries from the thread
        """
        try:
            response = self.client.conversations_replies(
                channel=channel_id, ts=thread_ts
            )
            messages: list[dict[str, Any]] = response.get("messages", [])
            self.log.info(f"Retrieved {len(messages)} messages from thread {thread_ts}")
            return messages
        except SlackApiError as e:
            self.log.error(f"Error fetching thread conversation: {e.response['error']}")
            return []

    def replace_user_mentions_with_names(self, text: str) -> str:
        """Replace user mentions like <@U123> with @Real Name <U123>.

        Args:
            text: The text containing user mentions

        Returns:
            Text with user mentions replaced with real names
        """
        import re

        def replace_mention(match: Any) -> str:
            user_id = match.group(1)
            try:
                real_name = self.get_user_real_name(user_id)
                return f"@{real_name} <{user_id}>"
            except Exception as e:
                self.log.warning(f"Could not get real name for user {user_id}: {e}")
                return str(match.group(0))  # Return original mention if error

        # Pattern to match <@USER_ID>
        mention_pattern = r"<@([A-Z0-9]+)>"
        return re.sub(mention_pattern, replace_mention, text)

    def _create_markdown_block(self, text: str) -> dict[str, Any]:
        """Create a single Slack markdown block.

        Args:
            text: The markdown text content

        Returns:
            A Slack markdown block dictionary
        """
        return {"type": "markdown", "text": text}

    def create_slack_message_from_api(
        self,
        slack_msg: dict[str, Any],
        channel_id: str,
        fallback_username: str = "unknown",
    ) -> Any:
        """Create a SlackMessage from a Slack API message response.

        Args:
            slack_msg: Raw message from Slack API (conversations_replies, etc.)
            channel_id: The channel ID
            fallback_username: Username to use if resolution fails

        Returns:
            SlackMessage object
        """
        from datetime import datetime

        from entrypoints.slack_entrypoint.slack_bot_service import SlackMessage

        message_id = slack_msg.get("ts", "")
        timestamp = (
            datetime.fromtimestamp(float(message_id), UTC)
            if message_id
            else datetime.now(UTC)
        )

        # Get user info
        user_id = slack_msg.get("user", "")
        try:
            username = (
                self.get_user_real_name(user_id) if user_id else fallback_username
            )
        except Exception:
            username = fallback_username

        # Process content to replace user mentions with real names
        raw_content = slack_msg.get("text", "")
        processed_content = (
            self.replace_user_mentions_with_names(raw_content) if raw_content else ""
        )

        return SlackMessage(
            channel_id=channel_id,
            message_id=message_id,
            user_id=user_id,
            username=username,
            content=processed_content,
            timestamp=timestamp,
            thread_ts=slack_msg.get("thread_ts", message_id),
            is_from_bot=user_id == self.bot_id,
        )

    def _create_text_blocks(self, text: str) -> list[dict[str, Any]]:
        """Create Slack blocks for text, splitting if necessary to handle length limits.

        Args:
            text: The text to convert to blocks

        Returns:
            List of Slack block dictionaries
        """
        # Slack markdown blocks have a 12000 character limit
        MAX_BLOCK_LENGTH = 12000

        if len(text) <= MAX_BLOCK_LENGTH:
            return [self._create_markdown_block(text)]

        # Split long text into multiple blocks
        blocks: list[dict[str, Any]] = []
        lines = text.split("\n")
        current_block_text = ""

        for line in lines:
            # Check if adding this line would exceed the limit
            test_text = current_block_text + ("\n" if current_block_text else "") + line

            if len(test_text) <= MAX_BLOCK_LENGTH:
                current_block_text = test_text
            else:
                # Save current block if it has content
                if current_block_text.strip():
                    blocks.append(self._create_markdown_block(current_block_text))

                # Start new block with current line
                # If single line is too long, truncate it
                if len(line) > MAX_BLOCK_LENGTH:
                    line = line[: MAX_BLOCK_LENGTH - 3] + "..."
                current_block_text = line

        # Add final block if it has content
        if current_block_text.strip():
            blocks.append(self._create_markdown_block(current_block_text))

        return blocks

    def _log_message_error(
        self,
        error_code: str,
        text: str,
        blocks: list[dict[str, Any]],
        fallback_text: str,
        operation: str,
        **params: Any,
    ) -> None:
        """Log detailed message content when Slack API errors occur."""
        self.log.error(f"Error {operation} message: {error_code}")
        self.log.error(f"Failed message content (length: {len(text)}): {text}")
        self.log.error(f"Generated blocks count: {len(blocks)}")
        for i, block in enumerate(blocks):
            block_text = block.get("text", "")
            self.log.error(f"Block {i} length: {len(block_text)}")
        self.log.error(f"Fallback text length: {len(fallback_text)}")
        param_strs = [f"{k}={v}" for k, v in params.items()]
        self.log.error(f"{operation.title()} parameters: {', '.join(param_strs)}")

    def send_reply(self, channel_id: str, thread_ts: str, text: str) -> str | None:
        """Send a reply in a thread with markdown formatting support.

        Args:
            channel_id (str): The channel ID to send the reply to
            thread_ts (str): The timestamp of the thread to reply to
            text (str): The text content of the reply (supports standard markdown)

        Returns:
            str or None: The timestamp of the sent message if successful, None otherwise
        """
        try:
            # Create blocks with automatic text splitting
            blocks = self._create_text_blocks(text)

            # Slack text parameter has a 40,000 character limit
            fallback_text = text if len(text) < 3000 else text[:2996] + "..."

            message_params: dict[str, Any] = {
                "channel": channel_id,
                "text": fallback_text,  # Fallback for notifications (truncated if needed)
                "blocks": blocks,
                "thread_ts": thread_ts,
            }

            # Send the message
            response = self.client.chat_postMessage(**message_params)
            message_ts = response["ts"]
            self.log.info(
                f"Reply sent in thread {thread_ts} with timestamp {message_ts}"
            )
            return cast("str", message_ts)
        except SlackApiError as e:
            self._log_message_error(
                error_code=e.response["error"],
                text=text,
                blocks=blocks,
                fallback_text=fallback_text,
                operation="sending",
                channel=channel_id,
                thread_ts=thread_ts,
            )
            return None

    def update_message(
        self,
        channel_id: str,
        message_ts: str,
        text: str,
        thread_ts: str | None = None,  # noqa: ARG002
    ) -> str | None:
        """Update an existing message with markdown formatting support.

        Args:
            channel_id (str): The channel ID containing the message
            message_ts (str): The timestamp of the message to update
            text (str): The new text content (supports standard markdown)
            thread_ts (str | None): The timestamp of the thread (unused but kept for compatibility)

        Returns:
            str or None: The timestamp of the updated message if successful, None otherwise
        """
        try:
            # Create blocks with automatic text splitting
            blocks = self._create_text_blocks(text)

            # Use same 3000 char limit as send_reply for consistency
            fallback_text = text if len(text) < 3000 else text[:2996] + "..."

            update_params: dict[str, Any] = {
                "channel": channel_id,
                "ts": message_ts,
                "text": fallback_text,  # Fallback for notifications (truncated if needed)
                "blocks": blocks,
            }

            # Update the message
            response = self.client.chat_update(**update_params)
            updated_ts = response["ts"]
            self.log.info(f"Message {message_ts} updated successfully")
            return cast("str", updated_ts)
        except SlackApiError as e:
            self._log_message_error(
                error_code=e.response["error"],
                text=text,
                blocks=blocks,
                fallback_text=fallback_text,
                operation="updating",
                channel=channel_id,
                ts=message_ts,
            )
            return None

    def post_canvas(
        self,
        channel_id: str,
        title: str | None = None,
        markdown_content: str | None = None,
        thread_ts: str | None = None,
        post_message: bool = True,
    ) -> str | None:
        """Create a new Slack canvas and optionally post it to a thread.

        Creates a standalone canvas, sets channel access, and posts a permalink message
        to make the canvas visible in the thread.

        Args:
            channel_id: The channel ID to post the canvas to
            title: Title for the canvas
            markdown_content: The markdown content for the canvas
            thread_ts: Thread timestamp to post the canvas link to (optional)
            post_message: Whether to post a message with the canvas permalink

        Returns:
            str or None: The canvas ID if successful, None otherwise
        """
        try:
            # Prepare document content if provided
            document_content = None
            if markdown_content:
                document_content = {"type": "markdown", "markdown": markdown_content}

            # Create a standalone canvas using canvases.create (not channel canvas)
            canvas_params: dict[str, Any] = {}
            if title:
                canvas_params["title"] = title
            if document_content:
                canvas_params["document_content"] = document_content

            response = self.client.canvases_create(**canvas_params)
            canvas_id = cast("str | None", response.get("canvas_id"))

            if not canvas_id:
                self.log.error("Canvas creation failed - no canvas_id returned")
                return None

            self.log.info(f"Standalone canvas created successfully: {canvas_id}")

            if post_message:
                # Step 1: Set access for channel and cached users
                try:
                    cached_user_ids = list(self.user_info_cache.keys())
                    self.client.canvases_access_set(
                        canvas_id=canvas_id,
                        channel_ids=[channel_id],
                        user_ids=cached_user_ids,
                        access_level="edit",
                    )
                    user_info = (
                        f" and {len(cached_user_ids)} users" if cached_user_ids else ""
                    )
                    self.log.info(
                        f"Canvas access set for channel {channel_id}{user_info}"
                    )
                except SlackApiError as e:
                    self.log.warning(
                        f"Failed to set canvas access: {e.response['error']}"
                    )
                    # Continue anyway - might still work

                # Step 2: Get the canvas permalink
                try:
                    file_info = self.client.files_info(file=canvas_id)
                    permalink = file_info["file"]["permalink"]
                    self.log.info(f"Canvas permalink retrieved: {permalink}")

                    # Step 3: Post message with permalink to thread
                    message_text = (
                        f"📄 {title or 'Canvas'}: {permalink}"
                        if title
                        else f"📄 Canvas: {permalink}"
                    )

                    if thread_ts:
                        # Post to specific thread
                        message_response = self.client.chat_postMessage(
                            channel=channel_id,
                            thread_ts=thread_ts,
                            text=message_text,
                            unfurl_links=True,
                        )
                    else:
                        # Post to channel
                        message_response = self.client.chat_postMessage(
                            channel=channel_id,
                            text=message_text,
                            unfurl_links=True,
                        )

                    if message_response["ok"]:
                        self.log.info("Canvas permalink posted successfully")
                    else:
                        self.log.warning(
                            f"Failed to post canvas permalink: {message_response.get('error', 'unknown error')}"
                        )

                except SlackApiError as e:
                    self.log.warning(
                        f"Failed to post canvas permalink: {e.response['error']}"
                    )
                    # Canvas was created successfully, so still return the ID

            return canvas_id

        except SlackApiError as e:
            error_code = e.response["error"]
            self.log.error(f"Error creating canvas: {error_code}")
            self.log.error(f"Canvas parameters - title: {title}")
            if markdown_content:
                self.log.error(f"Content length: {len(markdown_content)}")

            return None

    def is_bot_mentioned(self, content: str) -> bool:
        """Check if the bot was mentioned using proper Slack mention format.

        Only detects actual Slack mentions (e.g., <@BOTID>), not plain text
        containing the bot's name.
        """
        if self.bot_mention and content:
            return self.bot_mention in content
        return False

    def add_reaction(self, channel_id: str, message_ts: str, emoji_name: str) -> bool:
        """Add an emoji reaction to a message.

        Args:
            channel_id: The channel containing the message
            message_ts: The message timestamp
            emoji_name: The emoji name without colons (e.g., "eyes" not ":eyes:")

        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.reactions_add(
                channel=channel_id,
                timestamp=message_ts,
                name=emoji_name,
            )
            return True
        except SlackApiError as e:
            self.log.warning(
                f"Failed to add reaction '{emoji_name}': {e.response['error']}"
            )
            return False

    def remove_reaction(
        self, channel_id: str, message_ts: str, emoji_name: str
    ) -> bool:
        """Remove an emoji reaction from a message.

        Args:
            channel_id: The channel containing the message
            message_ts: The message timestamp
            emoji_name: The emoji name without colons (e.g., "eyes" not ":eyes:")

        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.reactions_remove(
                channel=channel_id,
                timestamp=message_ts,
                name=emoji_name,
            )
            return True
        except SlackApiError as e:
            # Don't log error for "no_reaction" - expected if already removed
            if e.response["error"] != "no_reaction":
                self.log.warning(
                    f"Failed to remove reaction '{emoji_name}': {e.response['error']}"
                )
            return False

    def set_message_callback(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Set the callback function for processing new messages."""
        self.message_callback = callback

    def start_socket_client(self) -> None:
        """Start the Socket Mode client in a background thread."""
        threading.Thread(target=self.socket_client.connect, daemon=True).start()

    def _socket_event_handler(
        self, client: BaseSocketModeClient, req: SocketModeRequest
    ) -> None:
        """Acknowledge and process Socket Mode events directly."""
        response = SocketModeResponse(envelope_id=req.envelope_id)
        client.send_socket_mode_response(response)
        event = req.payload.get("event", {})
        if (
            req.type == "events_api"
            and event.get("type") == "message"
            and "subtype" not in event
            and "bot_id" not in event
            and self.message_callback
        ):
            try:
                # Convert to standardized format
                user_id = event.get("user", "")
                try:
                    user_name = self.get_user_real_name(user_id)
                except Exception:
                    user_name = "unknown"

                channel_id = event.get("channel", "")
                thread_ts = event.get("thread_ts", event.get("ts"))
                message_data = {
                    "channelId": channel_id,
                    "messageId": event.get("ts"),
                    "username": user_name,
                    "userId": user_id,
                    "content": event.get("text", ""),
                    "thread_ts": thread_ts,
                }
                self.message_callback(message_data)
            except Exception as e:
                self.log.error(f"Error processing message callback: {str(e)}")

    def set_shutdown_callback(self, callback: Callable[[], None]) -> None:
        """Set callback to trigger application shutdown on critical errors."""
        self._shutdown_callback = callback

    def reset_connection_failures(self) -> None:
        """Reset failure counter after successful message processing."""
        with self._failure_lock:
            if self._consecutive_failures > 0:
                self.log.info(
                    f"Connection stable. Resetting failure counter "
                    f"(was {self._consecutive_failures})"
                )
                self._consecutive_failures = 0

    def _handle_socket_error(self, error: Exception) -> None:
        """Track consecutive BrokenPipeErrors and trigger shutdown after threshold.

        This method is called by the Socket Mode client's error listener when
        connection errors occur. It tracks BrokenPipeError occurrences and
        triggers application shutdown after reaching the configured threshold,
        allowing Docker to restart the container.
        """
        if isinstance(error, BrokenPipeError):
            with self._failure_lock:
                self._consecutive_failures += 1
                self.log.error(
                    f"BrokenPipeError ({self._consecutive_failures}/"
                    f"{self._max_connection_failures}): {error}"
                )
                if self._consecutive_failures >= self._max_connection_failures:
                    self.log.error(
                        "Max connection failures reached. Triggering shutdown."
                    )
                    if self._shutdown_callback:
                        self._shutdown_callback()
        else:
            self.log.warning(f"Socket error: {type(error).__name__}: {error}")

    def register_bot_conversation(self, thread_id: str, sender_id: str) -> None:
        """Register a new bot conversation thread."""
        if self._participant_tracker:
            self._participant_tracker.register_thread(thread_id, sender_id)

    def should_process_thread_reply(
        self,
        thread_id: str,
        channel_id: str,
        message_content: str,
    ) -> ThreadReplyDecision:
        """Decide if thread reply should be processed."""
        # No tracker = always process
        if not self._participant_tracker:
            return ThreadReplyDecision(should_process=True)

        bot_mentioned = self.is_bot_mentioned(message_content)
        is_registered = self._participant_tracker.is_registered(thread_id)

        # Case 1: Bot mentioned → always process
        if bot_mentioned:
            conversation = self.get_thread_conversation(channel_id, thread_id)
            if not is_registered:
                self._register_thread_from_conversation(thread_id, conversation)
            self._update_participants(thread_id, conversation)
            self.log.info(f"Processing thread {thread_id}: bot mentioned")
            return ThreadReplyDecision(should_process=True, conversation=conversation)

        # Case 2: Not registered → skip
        if not is_registered:
            self.log.debug(f"Skipping thread {thread_id}: not registered")
            return ThreadReplyDecision(should_process=False)

        # Case 3: Registered, no mention → check if private conversation
        requires_mention, loaded_conversation = self._requires_mention(
            thread_id, channel_id
        )
        if requires_mention:
            self.log.info(
                f"Skipping thread {thread_id}: multiple participants, mention required"
            )
            return ThreadReplyDecision(should_process=False)

        self.log.info(f"Processing thread {thread_id}: private conversation")
        return ThreadReplyDecision(
            should_process=True, conversation=loaded_conversation
        )

    def _requires_mention(
        self, thread_id: str, channel_id: str
    ) -> tuple[bool, list[dict[str, Any]] | None]:
        """Check if thread requires mention to process.

        Returns (requires_mention, conversation_if_loaded).
        """
        if not self._participant_tracker:
            return False, None

        # Fast path: 2+ cached participants → mention required
        cached_count = self._participant_tracker.get_participant_count(thread_id)
        if cached_count >= 2:
            return True, None

        # Slow path: load conversation to verify
        conversation = self.get_thread_conversation(channel_id, thread_id)
        participants = self._participant_tracker.extract_participants(conversation)
        self._participant_tracker.update_participants(thread_id, participants)

        return len(participants) >= 2, conversation

    def _update_participants(
        self, thread_id: str, conversation: list[dict[str, Any]]
    ) -> None:
        """Extract and update participants from conversation."""
        if self._participant_tracker:
            participants = self._participant_tracker.extract_participants(conversation)
            self._participant_tracker.update_participants(thread_id, participants)

    def _register_thread_from_conversation(
        self, thread_id: str, conversation: list[dict[str, Any]]
    ) -> None:
        """Register thread using first human message sender.

        Used when bot is mentioned in an unregistered thread.
        """
        if self._participant_tracker and conversation:
            for msg in conversation:
                user_id = msg.get("user", "")
                if user_id and user_id != self.bot_id:
                    self._participant_tracker.register_thread(thread_id, user_id)
                    return
