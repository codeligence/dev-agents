# Copyright (C) 2025 Codeligence
#
# This file is part of Dev Agents.
#
# Dev Agents is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Dev Agents is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Dev Agents.  If not, see <https://www.gnu.org/licenses/>.


from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC
from typing import Any, cast
import json
import threading

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.client import BaseSocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse

from core.log import get_logger
from integrations.slack.models import SlackBotConfig


@dataclass
class Attachment:
    """Class representing a file attachment to be sent to Slack."""

    filename: str
    content: str


class SlackClientService:
    def __init__(self, slack_config: SlackBotConfig):
        # Setup logging using centralized log file path utility
        self.log = get_logger(logger_name="SlackClientService", level="INFO")
        # Logging configuration is now DRY and managed in one place via get_log_file_path.
        self.user_info_cache: dict[str, dict[str, Any]] = {}  # Cache for user info

        # Load Slack tokens from config
        if not slack_config:
            raise ValueError("SlackClientService requires slack_config parameter")

        self.bot_token = slack_config.get_bot_token()
        self.channel_id = slack_config.get_channel_id()
        app_token = slack_config.get_app_token()

        self.client = WebClient(token=self.bot_token)
        self.user_info_cache = {}

        # Message callback for real-time processing
        self.message_callback: Callable[[dict[str, Any]], None] | None = None

        # Initialize Socket Mode client
        self.socket_client = SocketModeClient(
            app_token=app_token, web_client=self.client
        )

        # enable to see all slack logs

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

        from entrypoints.slack_models.slack_bot_service import SlackMessage

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

    def _upload_attachment(
        self, attachment: Any, thread_ts: str | None = None
    ) -> dict[str, Any] | None:
        """Upload a file attachment to Slack.

        Args:
            attachment (Attachment): The attachment to upload
            thread_ts (str, optional): Thread timestamp if uploading to a thread

        Returns:
            dict or None: File info if upload successful, None otherwise
        """
        try:
            upload_params = {
                "channel": self.channel_id,
                "content": attachment.content,
                "filename": attachment.filename,
            }

            # Add thread_ts if provided
            if thread_ts:
                upload_params["thread_ts"] = thread_ts

            file_upload_response = self.client.files_upload_v2(**upload_params)
            file_info = file_upload_response["file"]
            self.log.info(f"File uploaded successfully: {file_info['url_private']}")
            return cast("dict[str, Any]", file_info)
        except SlackApiError as e:
            self.log.error(f"Error uploading file: {e.response['error']}")
            return None

    def _create_message_blocks(
        self, text: str, _file_info: dict[str, Any], _attachment: Any
    ) -> list[dict[str, Any]]:
        """Create message blocks with text and file attachment reference.

        Args:
            text (str): Message text
            file_info (dict): File information from upload
            attachment (Attachment): The attachment object

        Returns:
            list: List of block elements for Slack message
        """
        return [
            {"type": "section", "text": {"type": "mrkdwn", "text": text}},
        ]

    def send_reply(
        self, thread_ts: str, text: str, attachment: Any = None
    ) -> str | None:
        """Send a reply in a thread.

        Args:
            thread_ts (str): The timestamp of the thread to reply to
            text (str): The text content of the reply
            attachment (Attachment, optional): File attachment to include with the message

        Returns:
            str or None: The timestamp of the sent message if successful, None otherwise
        """
        try:
            # Prepare message parameters
            message_params: dict[str, Any] = {
                "channel": self.channel_id,
                "text": text,
                "thread_ts": thread_ts,
            }

            # Handle attachment if provided
            if attachment:
                file_info = self._upload_attachment(attachment, thread_ts)
                if file_info:
                    blocks = self._create_message_blocks(text, file_info, attachment)
                    message_params["blocks"] = json.dumps(blocks)

            # Send the message
            response = self.client.chat_postMessage(**message_params)
            message_ts = response["ts"]
            self.log.info(
                f"Reply sent in thread {thread_ts} with timestamp {message_ts}"
            )
            return cast("str", message_ts)
        except SlackApiError as e:
            error = e.response["error"]
            self.log.error(f"Error sending message: {error}")
            # Optionally, log the problematic blocks for debugging
            if message_params and "blocks" in message_params:
                self.log.error(f"Blocks sent: {message_params['blocks']}")
            return None

    def update_message(
        self, thread_ts: str, message_ts: str, text: str, attachment: Any = None
    ) -> str | None:
        """Update an existing message.

        Returns:
            str or None: The timestamp of the updated message if successful, None otherwise
        """
        try:
            # Prepare update parameters
            update_params: dict[str, Any] = {
                "channel": self.channel_id,
                "ts": message_ts,
                "text": text,
            }

            # Handle attachment if provided
            if attachment:
                file_info = self._upload_attachment(attachment, thread_ts)
                if file_info:
                    update_params["blocks"] = json.dumps(
                        self._create_message_blocks(text, file_info, attachment)
                    )

            # Update the message
            response = self.client.chat_update(**update_params)
            updated_ts = response["ts"]
            self.log.info(f"Message {message_ts} updated successfully")
            return cast("str", updated_ts)
        except SlackApiError as e:
            self.log.error(f"Error updating message: {e.response['error']}")
            return None

    def is_bot_mentioned(self, content: str) -> bool:
        if self.bot_mention and content and self.bot_id:
            display_name = self.get_user_real_name(self.bot_id)
            return (
                self.bot_mention in content
                or display_name in content
                or self.bot_id in content
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
        if req.type == "events_api" and event.get("type") == "message":
            #  Only accept messages from the configured channel
            if (
                "subtype" not in event
                and "bot_id" not in event
                and event.get("channel") == self.channel_id
            ):
                if self.message_callback:
                    try:
                        # Convert to standardized format
                        user_id = event.get("user", "")
                        try:
                            user_name = self.get_user_real_name(user_id)
                        except Exception:
                            user_name = "unknown"

                        thread_ts = event.get("thread_ts", event.get("ts"))
                        message_data = {
                            "channelId": self.channel_id,
                            "messageId": event.get("ts"),
                            "username": user_name,
                            "userId": user_id,
                            "content": event.get("text", ""),
                            "thread_ts": thread_ts,
                        }
                        self.message_callback(message_data)
                    except Exception as e:
                        self.log.error(f"Error processing message callback: {str(e)}")
            else:
                self.log.debug(f"Ignored message from channel {event.get('channel')}")
