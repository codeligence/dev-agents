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


"""AG-UI implementation of AgentExecutionContext."""

from typing import Any
import asyncio
import uuid

from ag_ui.core import (
    CustomEvent,
    Event,
    EventType,
    StepFinishedEvent,
    StepStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
)

from core.config import BaseConfig
from core.log import get_logger
from core.message import MessageList
from core.prompts import BasePrompts
from core.protocols.agent_protocols import AgentExecutionContext

logger = get_logger("AGUIAgentContext")


class AGUIAgentContext(AgentExecutionContext):
    """AG-UI specific implementation of AgentExecutionContext.

    Emits AG-UI protocol events when send_status() and send_response() are called.
    Uses async queue to communicate events back to the main generator.
    """

    def __init__(
        self,
        message_list: MessageList,
        config: BaseConfig,
        prompts: BasePrompts,
        thread_id: str = "default",
        run_id: str | None = None,
        event_queue: asyncio.Queue[Any] | None = None,
    ):
        self.message_list = message_list
        self.config = config
        self.prompts = prompts
        self.thread_id = thread_id
        self.run_id = run_id or str(uuid.uuid4())
        self.context_id = str(uuid.uuid4())

        # Event queue for streaming events back to the generator
        self.event_queue: asyncio.Queue[Any] = event_queue or asyncio.Queue()

        # Track current step and message state
        self.current_step: str | None = None
        self.current_message_id: str | None = None

        logger.info(
            f"Created AG-UI agent context: thread_id={thread_id}, run_id={self.run_id}, context_id={self.context_id}"
        )

    async def send_status(self, message: str) -> None:
        """Send agent execution status by emitting AG-UI events.

        This will emit StepStarted/StepFinished events or CustomEvent for status updates.

        Args:
            message: Status message to send
        """
        logger.info(f"Sending status: {message}")

        try:
            # If there's a current step, finish it first
            if self.current_step:
                await self._emit_event(
                    StepFinishedEvent(
                        type=EventType.STEP_FINISHED, step_name=self.current_step
                    )
                )

            # Start new step
            self.current_step = message
            await self._emit_event(
                StepStartedEvent(type=EventType.STEP_STARTED, step_name=message)
            )

            # Also emit as custom event for detailed progress tracking
            await self._emit_event(
                CustomEvent(
                    type=EventType.CUSTOM,
                    name="status_update",
                    value={
                        "message": message,
                        "timestamp": asyncio.get_event_loop().time(),
                    },
                )
            )

        except Exception as e:
            logger.error(f"Failed to emit status events: {str(e)}")

    async def send_response(self, response: str) -> None:
        """Send final response by emitting streaming text message events.

        This will emit TextMessageStart/Content/End events to stream the response.

        Args:
            response: Final response message
        """
        logger.info(f"Sending response: {response[:100]}...")

        try:
            # Finish current step if any
            if self.current_step:
                await self._emit_event(
                    StepFinishedEvent(
                        type=EventType.STEP_FINISHED, step_name=self.current_step
                    )
                )
                self.current_step = None

            # Create unique message ID for this response
            message_id = str(uuid.uuid4())
            self.current_message_id = message_id

            # Start text message
            await self._emit_event(
                TextMessageStartEvent(
                    type=EventType.TEXT_MESSAGE_START,
                    message_id=message_id,
                    role="assistant",
                )
            )

            # Stream content (for now, send all at once - could be chunked for real streaming)
            await self._emit_event(
                TextMessageContentEvent(
                    type=EventType.TEXT_MESSAGE_CONTENT,
                    message_id=message_id,
                    delta=response,
                )
            )

            # End text message
            await self._emit_event(
                TextMessageEndEvent(
                    type=EventType.TEXT_MESSAGE_END, message_id=message_id
                )
            )

            self.current_message_id = None

        except Exception as e:
            logger.error(f"Failed to emit response events: {str(e)}")
            raise Exception("Failed to send response via AG-UI events")

    async def _emit_event(self, event: Event) -> None:
        """Emit an event by putting it in the event queue.

        Args:
            event: AG-UI event to emit
        """
        try:
            await self.event_queue.put(event)
            logger.debug(f"Emitted event: {event.type}")
        except Exception as e:
            logger.error(f"Failed to emit event {event.type}: {str(e)}")

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

        Uses thread_id as the primary identifier for state persistence.

        Returns:
            Unique identifier that can be used for state persistence
        """
        return self.thread_id

    def get_event_queue(self) -> asyncio.Queue[Any]:
        """Get the event queue for retrieving emitted events.

        Returns:
            Asyncio queue containing emitted events
        """
        return self.event_queue

    def get_agui_info(self) -> dict[str, Any]:
        """Get AG-UI specific context information.

        Returns:
            Dictionary containing AG-UI thread and run information
        """
        return {
            "thread_id": self.thread_id,
            "run_id": self.run_id,
            "context_id": self.context_id,
        }
