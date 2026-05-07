from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from typing import Any, cast
import re

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient
import aiohttp

from core.log import get_logger
from integrations.slack.markdown_splitter import split_markdown_for_slack
from integrations.slack.models import SlackBotConfig
from integrations.slack.thread_participant_tracker import ThreadParticipantTracker

_USER_MENTION_PATTERN = re.compile(r"<@([A-Z0-9]+)>")


@dataclass
class ThreadReplyDecision:
    """Result of thread reply processing decision."""

    should_process: bool
    conversation: list[dict[str, Any]] | None = None


class SlackClientService:
    def __init__(
        self,
        slack_config: SlackBotConfig,
    ):
        self.log = get_logger(logger_name="SlackClientService", level="INFO")
        self.user_info_cache: dict[str, dict[str, Any]] = {}

        if not slack_config:
            raise ValueError("SlackClientService requires slack_config parameter")

        self.bot_token = slack_config.get_bot_token()
        self.app_token = slack_config.get_app_token()
        self._always_respond = slack_config.get_always_respond()

        self.client = AsyncWebClient(token=self.bot_token)

        self.bot_id: str | None = None
        self.bot_mention: str | None = None
        self._participant_tracker: ThreadParticipantTracker | None = None

    async def initialize(self) -> None:
        """Resolve the bot identity and wire up the participant tracker.

        Must be awaited once before the service is used so that
        ``bot_id`` / ``bot_mention`` are available for filters and
        ``ThreadParticipantTracker`` can be constructed. Propagates
        ``SlackApiError`` if auth lookup fails — the bot cannot operate
        without a resolved identity, so the caller must abort startup.
        """
        bot_info = await self.client.auth_test()
        self.bot_id = bot_info["user_id"]
        self.bot_mention = f"<@{self.bot_id}>"
        self.log.info(
            f"Bot ID: {self.bot_id}, mention: {self.bot_mention}, "
            f"name: {bot_info['user']}"
        )
        self._participant_tracker = ThreadParticipantTracker(bot_id=self.bot_id)

    async def get_user_real_name(self, user_id: str) -> str:
        if user_id in self.user_info_cache:
            user_info = self.user_info_cache[user_id]
        else:
            response = await self.client.users_info(user=user_id)
            if hasattr(response, "data") and isinstance(response.data, dict):
                user_info = response.data
            elif isinstance(response, dict):
                user_info = response
            else:
                user_info = {}
            self.user_info_cache[user_id] = user_info
        real_name = user_info.get("user", {}).get("real_name", "unknown")
        return str(real_name) if real_name is not None else "unknown"

    async def get_thread_conversation(
        self, channel_id: str, thread_ts: str
    ) -> list[dict[str, Any]]:
        """Get all messages in a thread conversation."""
        try:
            response = await self.client.conversations_replies(
                channel=channel_id, ts=thread_ts
            )
            messages: list[dict[str, Any]] = response.get("messages", [])
            self.log.info(f"Retrieved {len(messages)} messages from thread {thread_ts}")
            return messages
        except SlackApiError as e:
            self.log.error(f"Error fetching thread conversation: {e.response['error']}")
            return []

    async def replace_user_mentions_with_names(self, text: str) -> str:
        """Replace user mentions like <@U123> with @Real Name <U123>."""
        user_ids = set(_USER_MENTION_PATTERN.findall(text))
        if not user_ids:
            return text

        names: dict[str, str] = {}
        for user_id in user_ids:
            try:
                names[user_id] = await self.get_user_real_name(user_id)
            except Exception as e:
                self.log.warning(f"Could not get real name for user {user_id}: {e}")

        def replace(match: re.Match[str]) -> str:
            user_id = match.group(1)
            if user_id in names:
                return f"@{names[user_id]} <{user_id}>"
            return match.group(0)

        return _USER_MENTION_PATTERN.sub(replace, text)

    async def create_slack_message_from_api(
        self,
        slack_msg: dict[str, Any],
        channel_id: str,
        fallback_username: str = "unknown",
    ) -> Any:
        """Create a SlackMessage from a Slack API message response."""
        from datetime import datetime

        from entrypoints.slack_entrypoint.models import SlackMessage

        message_id = slack_msg.get("ts", "")
        timestamp = (
            datetime.fromtimestamp(float(message_id), UTC)
            if message_id
            else datetime.now(UTC)
        )

        user_id = slack_msg.get("user", "")
        try:
            username = (
                await self.get_user_real_name(user_id) if user_id else fallback_username
            )
        except Exception:
            username = fallback_username

        raw_content = slack_msg.get("text", "")
        processed_content = (
            await self.replace_user_mentions_with_names(raw_content)
            if raw_content
            else ""
        )

        files = slack_msg.get("files", [])
        if files:
            attachment_lines = []
            for f in files:
                file_id = f.get("id", "")
                file_name = f.get("name", "unknown")
                if file_id:
                    attachment_lines.append(
                        f"[#attachment id={file_id} name={file_name}]"
                    )
            if attachment_lines:
                processed_content = (
                    processed_content + "\n" + "\n".join(attachment_lines)
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

    @staticmethod
    def _build_message_payload(
        text: str, extra_blocks: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """Build the ``text`` (notification fallback, 3 000-char cap) and
        ``blocks`` kwargs shared by ``chat_postMessage`` and ``chat_update``.
        """
        fallback = text if len(text) < 3000 else text[:2996] + "..."
        blocks: list[dict[str, Any]] = [{"type": "markdown", "text": text}]
        if extra_blocks:
            blocks.extend(extra_blocks)
        return {
            "text": fallback,
            "blocks": blocks,
        }

    async def _post_chunk(
        self,
        channel_id: str,
        thread_ts: str,
        text: str,
        extra_blocks: list[dict[str, Any]] | None = None,
    ) -> str | None:
        """Post a single pre-sized chunk as one Slack message."""
        try:
            response = await self.client.chat_postMessage(
                channel=channel_id,
                thread_ts=thread_ts,
                **self._build_message_payload(text, extra_blocks=extra_blocks),
            )
            return cast("str", response["ts"])
        except SlackApiError as e:
            self.log.error(
                f"Slack post error: {e.response['error']} (len={len(text)})\n{text}"
            )
            return None

    async def send_reply(
        self,
        channel_id: str,
        thread_ts: str,
        text: str,
        include_feedback: bool = False,
    ) -> str | None:
        """Send a reply in a thread with markdown formatting support.

        Long content is split into multiple Slack messages at semantic
        boundaries (headings, paragraphs, lines) so each message fits
        Slack's 12 000-character markdown block limit. Sending stops at
        the first failed chunk.

        When ``include_feedback`` is True, feedback buttons are appended
        to the last chunk only.

        Returns:
            The timestamp of the first sent message if any, None otherwise.
        """
        chunks = split_markdown_for_slack(text)
        if not chunks:
            return None

        from integrations.slack.feedback_blocks import build_feedback_blocks

        feedback_blocks = build_feedback_blocks() if include_feedback else None
        last_index = len(chunks) - 1
        first_ts: str | None = None
        for index, chunk in enumerate(chunks):
            extra = feedback_blocks if (index == last_index) else None
            ts = await self._post_chunk(
                channel_id, thread_ts, chunk, extra_blocks=extra
            )
            if ts is None:
                return first_ts
            if first_ts is None:
                first_ts = ts

        if first_ts:
            suffix = f" ({len(chunks)} messages)" if len(chunks) > 1 else ""
            self.log.info(f"Reply sent in thread {thread_ts}: {first_ts}{suffix}")
        return first_ts

    async def update_message(
        self,
        channel_id: str,
        message_ts: str,
        text: str,
        thread_ts: str | None = None,
        include_feedback: bool = False,
    ) -> str | None:
        """Update an existing message with markdown formatting support.

        The first chunk replaces the existing message in place; any
        remaining chunks are posted as new replies in ``thread_ts``.
        If overflow chunks exist but ``thread_ts`` is not provided,
        they are dropped with a warning.

        When ``include_feedback`` is True, feedback buttons are appended
        to whichever chunk ends up last (overflow tail or, if none, the
        in-place updated message).
        """
        chunks = split_markdown_for_slack(text)
        if not chunks:
            return None

        from integrations.slack.feedback_blocks import build_feedback_blocks

        feedback_blocks = build_feedback_blocks() if include_feedback else None
        has_overflow = len(chunks) > 1 and thread_ts is not None
        first_extra = feedback_blocks if (not has_overflow) else None

        first = chunks[0]
        try:
            response = await self.client.chat_update(
                channel=channel_id,
                ts=message_ts,
                **self._build_message_payload(first, extra_blocks=first_extra),
            )
            updated_ts = cast("str", response["ts"])
            self.log.info(f"Message {message_ts} updated successfully")
        except SlackApiError as e:
            self.log.error(
                f"Slack update error: {e.response['error']} "
                f"(len={len(first)})\n{first}"
            )
            return None

        if len(chunks) > 1:
            if not thread_ts:
                self.log.warning(
                    f"Discarding {len(chunks) - 1} overflow chunks; "
                    "no thread_ts provided"
                )
            else:
                last_index = len(chunks) - 1
                for index in range(1, len(chunks)):
                    extra = feedback_blocks if (index == last_index) else None
                    if (
                        await self._post_chunk(
                            channel_id, thread_ts, chunks[index], extra_blocks=extra
                        )
                        is None
                    ):
                        break

        return updated_ts

    async def post_canvas(
        self,
        channel_id: str,
        title: str | None = None,
        markdown_content: str | None = None,
        thread_ts: str | None = None,
        post_message: bool = True,
        include_feedback: bool = False,
    ) -> str | None:
        """Create a new Slack canvas and optionally post it to a thread."""
        try:
            document_content = None
            if markdown_content:
                document_content = {"type": "markdown", "markdown": markdown_content}

            canvas_params: dict[str, Any] = {}
            if title:
                canvas_params["title"] = title
            if document_content:
                canvas_params["document_content"] = document_content

            response = await self.client.canvases_create(**canvas_params)
            canvas_id = cast("str | None", response.get("canvas_id"))

            if not canvas_id:
                self.log.error("Canvas creation failed - no canvas_id returned")
                return None

            self.log.info(f"Standalone canvas created successfully: {canvas_id}")

            if post_message:
                try:
                    cached_user_ids = list(self.user_info_cache.keys())
                    await self.client.canvases_access_set(
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

                try:
                    file_info = await self.client.files_info(file=canvas_id)
                    permalink = file_info["file"]["permalink"]
                    self.log.info(f"Canvas permalink retrieved: {permalink}")

                    message_text = (
                        f"📄 {title or 'Canvas'}: {permalink}"
                        if title
                        else f"📄 Canvas: {permalink}"
                    )

                    from integrations.slack.feedback_blocks import (
                        build_feedback_blocks,
                    )

                    extra_blocks = build_feedback_blocks() if include_feedback else None

                    common_kwargs: dict[str, Any] = {
                        "channel": channel_id,
                        "text": message_text,
                        "unfurl_links": True,
                    }
                    if extra_blocks is not None:
                        common_kwargs["blocks"] = [
                            {"type": "markdown", "text": message_text},
                            *extra_blocks,
                        ]
                    if thread_ts:
                        common_kwargs["thread_ts"] = thread_ts

                    message_response = await self.client.chat_postMessage(
                        **common_kwargs
                    )

                    if message_response["ok"]:
                        self.log.info("Canvas permalink posted successfully")
                    else:
                        self.log.warning(
                            f"Failed to post canvas permalink: "
                            f"{message_response.get('error', 'unknown error')}"
                        )

                except SlackApiError as e:
                    self.log.warning(
                        f"Failed to post canvas permalink: {e.response['error']}"
                    )

            return canvas_id

        except SlackApiError as e:
            error_code = e.response["error"]
            self.log.error(f"Error creating canvas: {error_code}")
            self.log.error(f"Canvas parameters - title: {title}")
            if markdown_content:
                self.log.error(f"Content length: {len(markdown_content)}")

            return None

    async def download_file(self, file_id: str, target_dir: Path) -> Path | None:
        """Download a Slack file by ID to a target directory."""
        try:
            file_info = await self.client.files_info(file=file_id)
            file_data: dict[str, Any] = file_info.get("file", {})

            download_url: str | None = file_data.get("url_private_download")
            original_name: str = file_data.get("name", "file")

            suffix = Path(original_name).suffix
            safe_name = f"{file_id}{suffix}" if suffix else file_id

            if not download_url:
                self.log.error(f"No download URL available for file {file_id}")
                return None

            if not download_url.startswith("https://"):
                self.log.error(
                    f"Refusing to download file {file_id}: URL scheme is not HTTPS"
                )
                return None

            timeout = aiohttp.ClientTimeout(total=120)
            headers = {"Authorization": f"Bearer {self.bot_token}"}
            async with (
                aiohttp.ClientSession(timeout=timeout, headers=headers) as session,
                session.get(download_url) as resp,
            ):
                resp.raise_for_status()
                payload = await resp.read()

            target_dir.mkdir(parents=True, exist_ok=True)
            file_path = target_dir / safe_name
            file_path.write_bytes(payload)
            self.log.info(f"Downloaded file {file_id} ({original_name}) to {file_path}")
            return file_path

        except SlackApiError as e:
            self.log.error(
                f"Slack API error downloading file {file_id}: {e.response['error']}"
            )
            return None
        except aiohttp.ClientError as e:
            self.log.error(f"HTTP error downloading file {file_id}: {e}")
            return None
        except Exception as e:
            self.log.error(f"Error downloading file {file_id}: {e}")
            return None

    def is_bot_mentioned(self, content: str) -> bool:
        """Check if the bot was mentioned using proper Slack mention format.

        Only detects actual Slack mentions (e.g., <@BOTID>), not plain text
        containing the bot's name.

        Returns True unconditionally when always_respond mode is enabled.
        """
        if self._always_respond:
            return True
        if self.bot_mention and content:
            return self.bot_mention in content
        return False

    async def add_reaction(
        self, channel_id: str, message_ts: str, emoji_name: str
    ) -> bool:
        """Add an emoji reaction to a message."""
        try:
            await self.client.reactions_add(
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

    async def remove_reaction(
        self, channel_id: str, message_ts: str, emoji_name: str
    ) -> bool:
        """Remove an emoji reaction from a message."""
        try:
            await self.client.reactions_remove(
                channel=channel_id,
                timestamp=message_ts,
                name=emoji_name,
            )
            return True
        except SlackApiError as e:
            if e.response["error"] != "no_reaction":
                self.log.warning(
                    f"Failed to remove reaction '{emoji_name}': {e.response['error']}"
                )
            return False

    def register_bot_conversation(self, thread_id: str, sender_id: str) -> None:
        """Register a new bot conversation thread."""
        if self._participant_tracker:
            self._participant_tracker.register_thread(thread_id, sender_id)

    async def should_process_thread_reply(
        self,
        thread_id: str,
        channel_id: str,
        message_content: str,
    ) -> ThreadReplyDecision:
        """Decide if thread reply should be processed."""
        if not self._participant_tracker:
            return ThreadReplyDecision(should_process=True)

        bot_mentioned = self.is_bot_mentioned(message_content)
        is_registered = self._participant_tracker.is_registered(thread_id)

        if bot_mentioned:
            conversation = await self.get_thread_conversation(channel_id, thread_id)
            if not is_registered:
                self._register_thread_from_conversation(thread_id, conversation)
            self._update_participants(thread_id, conversation)
            self.log.info(f"Processing thread {thread_id}: bot mentioned")
            return ThreadReplyDecision(should_process=True, conversation=conversation)

        if not is_registered:
            self.log.debug(f"Skipping thread {thread_id}: not registered")
            return ThreadReplyDecision(should_process=False)

        requires_mention, loaded_conversation = await self._requires_mention(
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

    async def _requires_mention(
        self, thread_id: str, channel_id: str
    ) -> tuple[bool, list[dict[str, Any]] | None]:
        """Check if thread requires mention to process.

        Returns (requires_mention, conversation_if_loaded).
        """
        if not self._participant_tracker:
            return False, None

        cached_count = self._participant_tracker.get_participant_count(thread_id)
        if cached_count >= 2:
            return True, None

        conversation = await self.get_thread_conversation(channel_id, thread_id)
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
