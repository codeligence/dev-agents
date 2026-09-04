"""Bolt-backed runtime that drives the Slack bot.

Owns the ``AsyncApp``, registers Bolt listeners and the Assistant
lifecycle, and runs the Socket Mode handler until shutdown.
"""

from collections import OrderedDict
from collections.abc import AsyncIterator
from typing import Any
import asyncio
import contextlib

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_bolt.middleware.assistant.async_assistant import AsyncAssistant

from core.log import get_logger, reset_context_token, set_context_token
from core.message import MessageList
from core.protocols.message_consumer_protocols import MessageConsumer
from entrypoints.slack_entrypoint.stop_command_handler import StopCommandHandler
from entrypoints.slack_entrypoint.thread_task_manager import ThreadTaskManager
from integrations.slack.feedback_blocks import FEEDBACK_ACTION_ID, FeedbackEvent
from integrations.slack.feedback_logger import log_feedback
from integrations.slack.models import SlackBotConfig
from integrations.slack.slack_client_service import SlackClientService

# Cap on remembered "already titled" assistant threads. Slack workspaces
# can spawn an unbounded number of assistant side-panel threads over the
# lifetime of the process; an LRU cap keeps memory flat without a TTL
# subsystem. The cap is generous: an entry costs ~80 bytes, and assistant
# threads we may re-encounter are typically the recently active ones.
_TITLED_THREADS_MAX = 4096


class SlackBotRuntime:
    """Drives the Slack bot via Bolt's ``AsyncApp`` + Socket Mode."""

    def __init__(
        self,
        consumer: MessageConsumer,
        slack_service: SlackClientService,
        slack_config: SlackBotConfig,
        processing_timeout: int,
    ):
        self.consumer = consumer
        self.slack_service = slack_service
        self.slack_config = slack_config
        self.processing_timeout = processing_timeout
        self.logger = get_logger("SlackBotRuntime")

        self.task_manager = ThreadTaskManager()
        self.stop_handler = StopCommandHandler(slack_service, self.task_manager)

        self.active_threads: set[str] = set()
        self.thread_locks: dict[str, asyncio.Lock] = {}
        self._thread_lock_refs: dict[str, int] = {}
        self.main_lock = asyncio.Lock()
        # LRU-bounded set of threads that have already received a derived
        # title. ``OrderedDict`` is used as an ordered set; values unused.
        self._titled_assistant_threads: OrderedDict[str, None] = OrderedDict()

        self.app = AsyncApp(token=slack_service.bot_token)
        self._register_listeners()
        self._register_assistant()

    async def run(self, shutdown_event: asyncio.Event) -> None:
        """Connect Socket Mode and run until ``shutdown_event`` is set."""
        if not self.slack_service.bot_token or not self.slack_service.app_token:
            self.logger.error("Missing Slack credentials; refusing to start")
            return

        await self.slack_service.initialize()

        handler = AsyncSocketModeHandler(self.app, self.slack_service.app_token)
        self.logger.info("Starting Socket Mode handler")
        await handler.connect_async()  # type: ignore[no-untyped-call]
        try:
            await shutdown_event.wait()
        finally:
            self.logger.info("Shutdown requested; closing Socket Mode handler")
            await handler.close_async()  # type: ignore[no-untyped-call]

    # ------------------------------------------------------------------
    # Bolt registrations
    # ------------------------------------------------------------------
    def _register_listeners(self) -> None:
        @self.app.event("message")
        async def on_message(event: dict[str, Any]) -> None:
            await self._handle_channel_message(event)

        @self.app.event("app_mention")
        async def on_app_mention() -> None:
            # Slack delivers both `message` and `app_mention` for the same
            # @-mention; the `message` handler already routes it. Registered
            # to suppress Bolt's "unhandled request" 404 noise.
            return

        @self.app.action(FEEDBACK_ACTION_ID)
        async def on_feedback(ack: Any, body: dict[str, Any]) -> None:
            await ack()
            self._record_feedback(body)

    def _register_assistant(self) -> None:
        assistant = AsyncAssistant()

        @assistant.thread_started
        async def on_thread_started(say: Any, set_suggested_prompts: Any) -> None:
            prompts = self.slack_config.get_suggested_prompts()
            if prompts:
                await set_suggested_prompts(prompts=prompts)
            welcome = self.slack_config.get_welcome_message()
            if welcome:
                await say(welcome)

        @assistant.thread_context_changed
        async def on_thread_context_changed(save_thread_context: Any) -> None:
            await save_thread_context()

        @assistant.user_message
        async def on_user_message(payload: dict[str, Any], set_title: Any) -> None:
            await self._handle_assistant_message(payload, set_title)

        self.app.assistant(assistant)

    # ------------------------------------------------------------------
    # Channel / group / im (non-Assistant) handling
    # ------------------------------------------------------------------
    async def _handle_channel_message(self, event: dict[str, Any]) -> None:
        # Trace every inbound message event so silent filter drops are
        # visible in the log. Without this, a misconfigured bot or
        # changed Slack event subscription looks identical to "no
        # messages arrived" — see ceo.log 2026-05-18 07:58–15:16.
        subtype = event.get("subtype")
        ts = event.get("ts", "")
        ch = event.get("channel", "")
        self.logger.info(
            f"message event: ts={ts} channel={ch} subtype={subtype} "
            f"user={event.get('user', '')!r}"
        )

        if subtype not in (None, "file_share"):
            self.logger.info(f"  drop: subtype={subtype!r} not handled")
            return
        user_id = event.get("user", "")
        if not user_id:
            self.logger.info("  drop: missing user id")
            return
        if user_id == self.slack_service.bot_id:
            self.logger.debug("  drop: message from bot itself")
            return

        content = event.get("text", "")
        channel_id = event.get("channel", "")
        message_id = event.get("ts", "")
        thread_ts = event.get("thread_ts", message_id)
        if not message_id or not channel_id:
            self.logger.info("  drop: missing ts or channel")
            return

        is_top_level = thread_ts == message_id
        if is_top_level:
            if not self.slack_service.is_bot_mentioned(content):
                self.logger.info(
                    f"  drop: top-level message without bot mention "
                    f"(bot_id={self.slack_service.bot_id})"
                )
                return
            self.slack_service.register_bot_conversation(thread_ts, user_id)
            preloaded: list[dict[str, Any]] | None = None
        else:
            if self.stop_handler.is_stop_command(content, thread_ts, message_id):
                await self.stop_handler.handle_stop(channel_id, thread_ts)
                return
            decision = await self.slack_service.should_process_thread_reply(
                thread_id=thread_ts,
                channel_id=channel_id,
                message_content=content,
            )
            if not decision.should_process:
                self.logger.info(
                    f"  drop: thread reply rejected by should_process_thread_reply "
                    f"thread={thread_ts}"
                )
                return
            preloaded = decision.conversation

        self.logger.info(f"Starting task for thread_id={thread_ts}")
        self.task_manager.start_task(
            thread_ts,
            self._process_channel_thread(channel_id, thread_ts, preloaded),
        )

    @contextlib.asynccontextmanager
    async def _hold_thread_lock(self, thread_id: str) -> AsyncIterator[None]:
        """Acquire the per-thread lock with refcounted cleanup.

        Lock entries are dropped from ``thread_locks`` once no task is
        holding or waiting on them, so the dict cannot grow unboundedly
        with thread cardinality.
        """
        async with self.main_lock:
            lock = self.thread_locks.get(thread_id)
            if lock is None:
                lock = asyncio.Lock()
                self.thread_locks[thread_id] = lock
            self._thread_lock_refs[thread_id] = (
                self._thread_lock_refs.get(thread_id, 0) + 1
            )
        try:
            async with lock:
                yield
        finally:
            async with self.main_lock:
                count = self._thread_lock_refs.get(thread_id, 0) - 1
                if count <= 0:
                    self.thread_locks.pop(thread_id, None)
                    self._thread_lock_refs.pop(thread_id, None)
                else:
                    self._thread_lock_refs[thread_id] = count

    def _remember_titled_thread(self, thread_id: str) -> bool:
        """Record that ``thread_id`` has been titled.

        Returns True if this is the first time we see the thread (caller
        should set the title), False if it was already titled. Bounded by
        ``_TITLED_THREADS_MAX`` via LRU eviction so the set cannot grow
        without bound across long-running processes.
        """
        titled = self._titled_assistant_threads
        if thread_id in titled:
            titled.move_to_end(thread_id)
            return False
        titled[thread_id] = None
        if len(titled) > _TITLED_THREADS_MAX:
            titled.popitem(last=False)
        return True

    async def _process_channel_thread(
        self,
        channel_id: str,
        thread_id: str,
        preloaded_conversation: list[dict[str, Any]] | None = None,
    ) -> None:
        """Process a channel/group/im thread end-to-end with eyes emoji."""
        last_message_ts: str | None = None
        try:
            async with asyncio.timeout(self.processing_timeout):
                async with self._hold_thread_lock(thread_id):
                    if thread_id in self.active_threads:
                        self.logger.info(
                            f"Thread {thread_id} is already being processed, skipping"
                        )
                        return
                    self.active_threads.add(thread_id)
                    token = set_context_token(thread_id)
                    try:
                        if preloaded_conversation is not None:
                            slack_messages = preloaded_conversation
                        else:
                            slack_messages = (
                                await self.slack_service.get_thread_conversation(
                                    channel_id, thread_id
                                )
                            )

                        if slack_messages:
                            last_message_ts = slack_messages[-1].get("ts")
                            if last_message_ts:
                                await self.slack_service.add_reaction(
                                    channel_id, last_message_ts, "eyes"
                                )

                        processed_messages = [
                            await self.slack_service.create_slack_message_from_api(
                                msg, channel_id
                            )
                            for msg in slack_messages
                        ]
                        message_list = MessageList(processed_messages)
                        self.logger.info(
                            f"Processing thread {thread_id} with {len(message_list)} messages"
                        )
                        await self.consumer.consume(message_list)
                        self.logger.info(f"Successfully processed thread {thread_id}")
                    except Exception as e:
                        self.logger.error(f"Error processing thread {thread_id}: {e}")
                        await self._notify_error(channel_id, thread_id)
                    finally:
                        if last_message_ts:
                            await self.slack_service.remove_reaction(
                                channel_id, last_message_ts, "eyes"
                            )
                        reset_context_token(token)
                        self.active_threads.discard(thread_id)
        except (TimeoutError, asyncio.CancelledError, Exception) as e:
            if isinstance(e, TimeoutError):
                self.logger.error(
                    f"Thread {thread_id} processing timed out "
                    f"after {self.processing_timeout}s"
                )
                await self._notify_error(channel_id, thread_id, timeout=True)
            elif isinstance(e, asyncio.CancelledError):
                self.logger.info(f"Thread {thread_id} processing cancelled")
            else:
                self.logger.error(
                    f"Unexpected error processing thread {thread_id}: {e}"
                )
                await self._notify_error(channel_id, thread_id)
            # These exceptions escape _hold_thread_lock, so active_threads
            # was never cleaned up by the inner finally block.
            self.active_threads.discard(thread_id)

    async def _notify_error(
        self, channel_id: str, thread_id: str, *, timeout: bool = False
    ) -> None:
        """Best-effort error notification to the user in the thread."""
        text = (
            "⚠️ Processing timed out. Please try again."
            if timeout
            else "⚠️ Something went wrong while processing your request."
        )
        try:
            await self.slack_service.send_reply(channel_id, thread_id, text)
        except Exception as notify_err:
            self.logger.warning(f"Failed to notify user of error: {notify_err}")

    # ------------------------------------------------------------------
    # Assistant container handling
    # ------------------------------------------------------------------
    async def _handle_assistant_message(
        self, payload: dict[str, Any], set_title: Any
    ) -> None:
        channel_id = payload.get("channel", "")
        thread_id = payload.get("thread_ts") or payload.get("ts", "")
        message_id = payload.get("ts", "")
        content = payload.get("text", "") or ""
        user_id = payload.get("user", "")

        if not channel_id or not thread_id:
            return
        if user_id == self.slack_service.bot_id:
            return

        if self.stop_handler.is_stop_command(
            content, thread_id, message_id, require_mention=False
        ):
            await self.stop_handler.handle_stop(channel_id, thread_id)
            return

        if self._remember_titled_thread(thread_id):
            title = content.strip()[:100] or "Conversation"
            try:
                await set_title(title=title)
            except Exception as e:
                self.logger.warning(f"Failed to set assistant thread title: {e}")

        self.logger.info(f"Starting assistant task for thread_id={thread_id}")
        self.task_manager.start_task(
            thread_id,
            self._process_assistant_thread(channel_id, thread_id),
        )

    async def _process_assistant_thread(self, channel_id: str, thread_id: str) -> None:
        """Process an Assistant-thread message reusing channel-thread flow.

        Status messages still post real updating messages so user-visible
        behaviour matches today's DM experience.
        """
        await self._process_channel_thread(
            channel_id, thread_id, preloaded_conversation=None
        )

    # ------------------------------------------------------------------
    # Feedback handling
    # ------------------------------------------------------------------
    def _record_feedback(self, body: dict[str, Any]) -> None:
        from core.hooks import hooks

        actions = body.get("actions") or []
        if not actions:
            return
        action = actions[0]
        value = action.get("selected_option", {}).get("value") or action.get(
            "value", ""
        )
        user = body.get("user", {})
        channel = body.get("channel", {})
        message = body.get("message", {})

        user_id = user.get("id", "")
        channel_id = channel.get("id", "")
        thread_ts = message.get("thread_ts")
        message_ts = message.get("ts")
        action_id = action.get("action_id", FEEDBACK_ACTION_ID)
        value_str = str(value)

        log_feedback(
            user_id=user_id,
            channel_id=channel_id,
            thread_ts=thread_ts,
            message_ts=message_ts,
            value=value_str,
            action_id=action_id,
        )

        event = FeedbackEvent(
            user_id=user_id,
            channel_id=channel_id,
            thread_ts=thread_ts,
            message_ts=message_ts,
            value=value_str,
            action_id=action_id,
            body=body,
        )
        hooks().do_action("slack.feedback", event=event)
