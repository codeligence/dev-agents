from dataclasses import dataclass
from datetime import datetime
from typing import Any
import asyncio
import queue
import signal
import threading

from core.log import get_logger, reset_context_token, set_context_token
from core.message import BaseMessage, MessageList
from core.protocols.message_consumer_protocols import MessageConsumer
from entrypoints.slack_entrypoint.stop_command_handler import StopCommandHandler
from entrypoints.slack_entrypoint.thread_task_manager import ThreadTaskManager
from integrations.slack.slack_client_service import (
    SlackClientService,
)


@dataclass
class SlackMessage(BaseMessage):
    """Concrete implementation of BaseMessage for Slack messages."""

    channel_id: str
    message_id: str  # Slack timestamp
    user_id: str
    username: str
    content: str
    timestamp: datetime
    thread_ts: str
    is_from_bot: bool = False

    def get_user_name(self) -> str:
        return self.username

    def get_user_id(self) -> str:
        return self.user_id

    def get_message_content(self) -> str:
        return self.content

    def get_message_date(self) -> datetime:
        return self.timestamp

    def get_thread_id(self) -> str:
        return self.thread_ts

    def is_bot(self) -> bool:
        return self.is_from_bot


class SlackBotService:
    """Core service for Slack bot message processing."""

    def __init__(
        self,
        consumer: MessageConsumer,
        slack_client: SlackClientService,
        processing_timeout: int = 6000,
        register_signal_handlers: bool = True,
    ):
        self.consumer = consumer
        self.slack_service = slack_client  # Use the existing instance
        self.processing_timeout = processing_timeout
        self.logger = get_logger("SlackBotService")

        # Task management with stop command support
        self.task_manager = ThreadTaskManager()
        self.stop_handler = StopCommandHandler(slack_client, self.task_manager)

        # Thread management
        self.active_threads: set[str] = set()
        self.thread_locks: dict[str, asyncio.Lock] = {}
        self.main_lock = asyncio.Lock()

        # Message queue for thread communication
        self.message_queue: queue.Queue[dict[str, Any]] = queue.Queue()

        # Shutdown management
        self.shutdown_event = (
            threading.Event()
        )  # Use threading.Event for cross-thread signaling
        self.asyncio_shutdown_event: asyncio.Event | None = (
            None  # Will be created in asyncio thread
        )
        self.asyncio_thread: threading.Thread | None = None
        self.asyncio_loop: asyncio.AbstractEventLoop | None = None

        # Set up message callback
        self.slack_service.set_message_callback(self._handle_new_message)

        # Set up shutdown callback for connection failure handling
        self.slack_service.set_shutdown_callback(self.shutdown)

        # Set up signal handlers for graceful shutdown (skip when managed by orchestrator)
        if register_signal_handlers:
            self._setup_signal_handlers()

    def start(self) -> None:
        """Start the Slack bot service with proper thread separation."""
        self.logger.info("Starting Slack Bot Service")

        # Validate Slack configuration
        if not self.slack_service.bot_token:
            self.logger.error("Missing Slack credentials. Please set SLACK_BOT_TOKEN")
            return

        self.logger.info("Slack bot credentials validated")

        # Start the asyncio thread for message processing
        self.logger.info("Starting asyncio message processing thread...")
        self.asyncio_thread = threading.Thread(
            target=self._run_asyncio_loop, daemon=False
        )
        self.asyncio_thread.start()

        # Start Socket Mode client for real-time messages (daemon thread)
        self.logger.info("Starting real-time message processing...")
        self.slack_service.start_socket_client()

        # Wait for shutdown signal in main thread
        self.logger.info("Service started successfully. Waiting for messages...")
        try:
            self.shutdown_event.wait()  # Block until shutdown
            self.logger.info("Shutdown event received, stopping service...")
        except Exception as e:
            self.logger.error(f"Error in service: {str(e)}")
            raise
        finally:
            # Signal asyncio thread to shutdown
            if (
                self.asyncio_loop
                and not self.asyncio_loop.is_closed()
                and self.asyncio_shutdown_event
            ):
                self.asyncio_loop.call_soon_threadsafe(self.asyncio_shutdown_event.set)

            # Wait for asyncio thread to finish
            if self.asyncio_thread and self.asyncio_thread.is_alive():
                self.asyncio_thread.join(timeout=5)

            self.logger.info("Slack Bot Service shutdown complete")

    def _handle_new_message(self, raw_message: dict[str, Any]) -> None:
        """Handle a new message from the Socket Mode client (runs in daemon thread)."""
        try:
            # Put raw message in queue for asyncio thread to process
            self.message_queue.put(raw_message)

            # Extract thread_ts for logging
            thread_ts = raw_message.get(
                "thread_ts", raw_message.get("messageId", "unknown")
            )
            self.logger.debug(f"Raw message queued for processing: {thread_ts}")

        except Exception as e:
            self.logger.error(f"Error handling new message: {str(e)}")

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""

        def signal_handler(signum: int, _frame: Any) -> None:
            self.logger.info(f"Received signal {signum}, initiating shutdown...")
            # Signal shutdown using threading.Event (thread-safe)
            self.shutdown_event.set()

        # Register handlers for common termination signals
        signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
        signal.signal(signal.SIGTERM, signal_handler)  # Process termination

    def shutdown(self) -> None:
        """Trigger graceful shutdown."""
        self.logger.info("Shutdown requested")
        self.shutdown_event.set()

    def _run_asyncio_loop(self) -> None:
        """Run the asyncio event loop in a dedicated thread."""
        # Create new event loop for this thread
        self.asyncio_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.asyncio_loop)

        # Create asyncio shutdown event in this loop
        self.asyncio_shutdown_event = asyncio.Event()

        try:
            self.logger.info("Asyncio message processing thread started")
            self.asyncio_loop.run_until_complete(self._message_queue_processor())
        except Exception as e:
            self.logger.error(f"Error in asyncio thread: {str(e)}")
        finally:
            self.asyncio_loop.close()
            self.logger.info("Asyncio message processing thread stopped")

    async def _message_queue_processor(self) -> None:
        """Process messages from queue in asyncio context."""
        while True:
            try:
                # Check for shutdown
                if self.asyncio_shutdown_event and self.asyncio_shutdown_event.is_set():
                    self.logger.info("Asyncio shutdown event received")
                    break

                # Collect all available messages from queue (batch processing)
                raw_messages = []
                try:
                    # Get first message (blocking with timeout)
                    raw_message = self.message_queue.get_nowait()
                    raw_messages.append(raw_message)

                    # Get all remaining messages (non-blocking)
                    while True:
                        try:
                            raw_message = self.message_queue.get_nowait()
                            raw_messages.append(raw_message)
                        except queue.Empty:
                            break

                except queue.Empty:
                    # No messages, wait briefly before checking again
                    await asyncio.sleep(0.2)
                    continue

                if raw_messages:
                    # Extract unique (channel_id, thread_id) pairs
                    unique_threads: set[tuple[str, str]] = set()
                    # Store preloaded conversations to avoid re-fetching
                    preloaded_conversations: dict[
                        tuple[str, str], list[dict[str, Any]]
                    ] = {}

                    for raw_message in raw_messages:
                        channel_id = raw_message.get("channelId", "unknown")
                        thread_id = raw_message.get(
                            "thread_ts", raw_message.get("messageId", "unknown")
                        )
                        message_id = raw_message.get("messageId", "unknown")
                        username = raw_message.get("username", "unknown")
                        sender_id = raw_message.get("userId", "unknown")
                        content = raw_message.get("content", "")
                        content_preview = content[:100]

                        self.logger.debug(
                            f"Raw message: {username}: {content_preview} (thread: {thread_id})"
                        )

                        # Check if this is a top-level message (not a thread response)
                        if thread_id == message_id:
                            # Top-level message: only process if bot is explicitly mentioned
                            if self.slack_service.is_bot_mentioned(content):
                                self.logger.info(
                                    f"Bot mentioned in top-level message from {username}, "
                                    f"registering thread {thread_id}"
                                )
                                self.slack_service.register_bot_conversation(
                                    thread_id, sender_id
                                )
                                unique_threads.add((channel_id, thread_id))
                            else:
                                self.logger.debug(
                                    f"Bot not mentioned in top-level message from {username}, skipping"
                                )
                        else:
                            # Thread reply: use participant-based filtering
                            decision = self.slack_service.should_process_thread_reply(
                                thread_id=thread_id,
                                channel_id=channel_id,
                                message_content=content,
                            )
                            if decision.should_process:
                                unique_threads.add((channel_id, thread_id))
                                if decision.conversation:
                                    preloaded_conversations[(channel_id, thread_id)] = (
                                        decision.conversation
                                    )

                    # Detect and handle stop commands first
                    stop_threads: set[tuple[str, str]] = set()
                    for raw_message in raw_messages:
                        content = raw_message.get("content", "")
                        message_id = raw_message.get("messageId", "unknown")
                        thread_id = raw_message.get("thread_ts", message_id)
                        if self.stop_handler.is_stop_command(
                            content, thread_id, message_id
                        ):
                            channel_id = raw_message.get("channelId", "unknown")
                            stop_threads.add((channel_id, thread_id))

                    for channel_id, thread_id in stop_threads:
                        self.stop_handler.handle_stop(channel_id, thread_id)
                        unique_threads.discard((channel_id, thread_id))

                    self.logger.info(
                        f"Processing {len(raw_messages)} raw messages into {len(unique_threads)} unique threads"
                    )

                    # Process each unique thread
                    for channel_id, thread_id in unique_threads:
                        self.logger.info(f"Starting task for thread_id={thread_id}")
                        preloaded = preloaded_conversations.get((channel_id, thread_id))
                        self.task_manager.start_task(
                            thread_id,
                            self._process_messages(thread_id, channel_id, preloaded),
                        )

            except Exception as e:
                self.logger.error(f"Error in message queue processor: {str(e)}")
                await asyncio.sleep(1)  # Wait before retrying

    async def _process_messages(
        self,
        thread_id: str,
        channel_id: str,
        preloaded_conversation: list[dict[str, Any]] | None = None,
    ) -> None:
        """Process messages for a specific thread with conversation loading and thread-safe locking."""
        # Get or create thread lock
        async with self.main_lock:
            if thread_id not in self.thread_locks:
                self.thread_locks[thread_id] = asyncio.Lock()
            thread_lock = self.thread_locks[thread_id]

        # Process thread with timeout
        try:
            async with asyncio.timeout(self.processing_timeout):
                async with thread_lock:
                    # Check if thread is already being processed
                    if thread_id in self.active_threads:
                        self.logger.info(
                            f"Thread {thread_id} is already being processed, skipping"
                        )
                        return

                    # Mark thread as active
                    self.active_threads.add(thread_id)

                    # Set logging context
                    token = set_context_token(thread_id)

                    # Track last message for processing indicator emoji
                    last_message_ts: str | None = None

                    try:
                        # Use preloaded conversation if available, otherwise fetch
                        if preloaded_conversation is not None:
                            self.logger.debug(
                                f"Using preloaded conversation for thread {thread_id}"
                            )
                            slack_messages = preloaded_conversation
                        else:
                            self.logger.info(
                                f"Loading conversation for thread {thread_id} in channel {channel_id}"
                            )
                            slack_messages = self.slack_service.get_thread_conversation(
                                channel_id, thread_id
                            )

                        # Add processing indicator emoji to the last message
                        if slack_messages:
                            last_message_ts = slack_messages[-1].get("ts")
                            if last_message_ts:
                                self.slack_service.add_reaction(
                                    channel_id, last_message_ts, "eyes"
                                )

                        # Convert to SlackMessage objects using existing method
                        processed_messages = [
                            self.slack_service.create_slack_message_from_api(
                                msg, channel_id
                            )
                            for msg in slack_messages
                        ]

                        # Create MessageList and call consumer
                        message_list = MessageList(processed_messages)
                        self.logger.info(
                            f"Processing thread {thread_id} with {len(message_list)} messages"
                        )

                        # Consume messages
                        await self.consumer.consume(message_list)

                        self.logger.info(f"Successfully processed thread {thread_id}")

                    except Exception as e:
                        self.logger.error(
                            f"Error processing thread {thread_id}: {str(e)}"
                        )

                    finally:
                        # Remove processing indicator emoji
                        if last_message_ts:
                            self.slack_service.remove_reaction(
                                channel_id, last_message_ts, "eyes"
                            )
                        # Clean up
                        reset_context_token(token)
                        self.active_threads.discard(thread_id)

        except TimeoutError:
            self.logger.error(
                f"Thread {thread_id} processing timed out after {self.processing_timeout}s"
            )
            self.active_threads.discard(thread_id)
        except asyncio.CancelledError:
            self.logger.info(f"Thread {thread_id} processing cancelled")
            self.active_threads.discard(thread_id)
            # Response is sent by stop_handler, task cleanup by task_manager
        except Exception as e:
            self.logger.error(
                f"Unexpected error processing thread {thread_id}: {str(e)}"
            )
            self.active_threads.discard(thread_id)
