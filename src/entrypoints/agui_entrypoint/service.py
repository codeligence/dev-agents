#!/usr/bin/env python3
"""AG-UI entrypoint for streaming agent events via HTTP.

Routes are registered on the shared HTTP server when configured.
"""

from collections.abc import AsyncGenerator
from typing import Any, cast
import asyncio
import traceback

from ag_ui.core import (
    EventType,
    RunAgentInput,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
)
from ag_ui.encoder import EventEncoder
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from agents.agents.gitchatbot.agent import AGENT_NAME
from core.config import BaseConfig, get_default_config
from core.log import get_logger, reset_context_token, set_context_token
from core.prompts import get_default_prompts
from entrypoints.agui_entrypoint.agent_context import AGUIAgentContext
from entrypoints.agui_entrypoint.message import convert_agui_messages_to_message_list
from entrypoints.http_server.auth import ApiKeyAuth
from entrypoints.shared.agent_setup import ensure_agents_registered

logger = get_logger("AGUIEntrypoint", level="INFO")

# Router — mounted on the shared HTTP app
router = APIRouter()


class AGUIConfig:
    """Configuration for AG-UI service."""

    def __init__(self, base_config: BaseConfig) -> None:
        self._base_config = base_config

    def get_default_timeout(self) -> int:
        return int(self._base_config.get_value("agui.agent.defaultTimeout", 300))

    def get_default_agent_type(self) -> str:
        return cast(
            "str",
            self._base_config.get_value("agui.agent.defaultAgentType", AGENT_NAME),
        )

    def get_max_message_length(self) -> int:
        return int(self._base_config.get_value("agui.agent.maxMessageLength", 10000))

    def get_auth(self) -> ApiKeyAuth:
        """Validated Bearer-token policy for ``/agent``.

        Raises:
            ConfigurationError: If ``agui.server.apiKeys`` is malformed or empty
                without ``agui.server.allowUnauthenticated``.
        """
        return ApiKeyAuth.from_config(self._base_config, "agui")

    def is_configured(self) -> bool:
        """Check if AGUI service is configured and enabled."""
        return self._base_config.get_bool("agui.server.enabled", False)


@router.post("/agent")
async def run_agent(input_data: RunAgentInput, request: Request) -> StreamingResponse:
    """Run an agent and stream events back to client.

    Args:
        input_data: AG-UI RunAgentInput containing messages, tools, context, etc.
        request: FastAPI request object for header information

    Returns:
        StreamingResponse with Server-Sent Events containing agent execution progress
    """

    logger.info(
        f"Received agent run request: thread_id={input_data.thread_id}, run_id={input_data.run_id}"
    )

    base_config = get_default_config()
    config_instance = AGUIConfig(base_config)

    # Same gate as the OpenAI entrypoint: this endpoint runs the agent, so it
    # must not be the one unauthenticated door on the shared HTTP server.
    if not config_instance.get_auth().is_authorized(
        request.headers.get("authorization", "")
    ):
        logger.warning("Rejected agent run request: invalid or missing API key")
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not input_data.thread_id or not input_data.run_id:
        logger.error("Missing required thread_id or run_id")
        raise HTTPException(
            status_code=400, detail="Missing required thread_id or run_id"
        )

    if not input_data.messages:
        logger.error("No messages provided in request")
        raise HTTPException(status_code=400, detail="At least one message is required")

    # Validate message length
    max_length = config_instance.get_max_message_length()
    for msg in input_data.messages:
        content = getattr(msg, "content", "")
        if content and len(content) > max_length:
            logger.error(
                f"Message content exceeds maximum length: {len(content)} > {max_length}"
            )
            raise HTTPException(
                status_code=400,
                detail=f"Message content exceeds maximum length of {max_length} characters",
            )

    # Create event encoder based on client Accept header
    accept_header = request.headers.get("accept") or "text/plain"
    encoder = EventEncoder(accept=accept_header)

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generator that yields AG-UI events as Server-Sent Events."""

        # Set logging context
        context_token = set_context_token(input_data.thread_id)

        try:
            # Start the run
            yield encoder.encode(
                RunStartedEvent(
                    type=EventType.RUN_STARTED,
                    thread_id=input_data.thread_id,
                    run_id=input_data.run_id,
                )
            )

            # Create event queue for agent context communication
            event_queue: asyncio.Queue[Any] = asyncio.Queue()

            # Convert AG-UI messages to our internal format
            message_list = convert_agui_messages_to_message_list(
                input_data.messages, input_data.thread_id
            )

            # Create AG-UI agent context
            agui_context = AGUIAgentContext(
                message_list=message_list,
                config=base_config,
                prompts=get_default_prompts(),
                thread_id=input_data.thread_id,
                run_id=input_data.run_id,
                event_queue=event_queue,
            )

            agent_type = config_instance.get_default_agent_type()
            timeout = config_instance.get_default_timeout()
            agent_service = ensure_agents_registered()

            logger.info(f"Executing agent: type={agent_type}, timeout={timeout}s")

            # Create task for agent execution
            agent_task = asyncio.create_task(
                agent_service.execute_agent_by_type(
                    agent_type=agent_type, context=agui_context, timeout_seconds=timeout
                )
            )

            # Stream events while agent is executing
            while not agent_task.done():
                try:
                    # Check for events with short timeout
                    event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                    yield encoder.encode(event)
                except TimeoutError:
                    # No events, continue checking if agent is done
                    continue
                except Exception as e:
                    logger.error(f"Error consuming events: {str(e)}")
                    break

            # Agent execution finished, drain any remaining events
            while not event_queue.empty():
                try:
                    event = event_queue.get_nowait()
                    yield encoder.encode(event)
                except asyncio.QueueEmpty:
                    break

            # Check if agent task had an exception
            try:
                await agent_task  # This will raise if there was an exception
            except Exception as agent_error:
                logger.error(f"Agent execution failed: {str(agent_error)}")
                yield encoder.encode(
                    RunErrorEvent(
                        type=EventType.RUN_ERROR,
                        message=f"Agent execution failed: {str(agent_error)}",
                        code="AGENT_EXECUTION_ERROR",
                    )
                )
                return

            # Success - emit run finished event
            yield encoder.encode(
                RunFinishedEvent(
                    type=EventType.RUN_FINISHED,
                    thread_id=input_data.thread_id,
                    run_id=input_data.run_id,
                )
            )

            logger.info(f"Agent run completed successfully: {input_data.run_id}")

        except TimeoutError:
            logger.error(f"Agent run timed out: {input_data.run_id}")
            yield encoder.encode(
                RunErrorEvent(
                    type=EventType.RUN_ERROR,
                    message="Agent execution timed out",
                    code="TIMEOUT_ERROR",
                )
            )
        except asyncio.CancelledError:
            logger.info(f"Agent run cancelled: {input_data.run_id}")
            yield encoder.encode(
                RunErrorEvent(
                    type=EventType.RUN_ERROR,
                    message="Agent execution was cancelled",
                    code="CANCELLED_ERROR",
                )
            )
        except ValueError as validation_error:
            logger.error(f"Invalid input data: {str(validation_error)}")
            yield encoder.encode(
                RunErrorEvent(
                    type=EventType.RUN_ERROR,
                    message=f"Invalid input: {str(validation_error)}",
                    code="VALIDATION_ERROR",
                )
            )
        except Exception as unexpected_error:
            error_traceback = traceback.format_exc()
            logger.error(
                f"Unexpected error in agent run: {str(unexpected_error)}\\n{error_traceback}"
            )
            yield encoder.encode(
                RunErrorEvent(
                    type=EventType.RUN_ERROR,
                    message=f"Unexpected error: {str(unexpected_error)}",
                    code="INTERNAL_ERROR",
                )
            )

        finally:
            reset_context_token(context_token)

    return StreamingResponse(
        event_generator(),
        media_type=encoder.get_content_type(),  # "text/event-stream"
    )


# ── Self-registration ───────────────────────────────────────────────────────


def register_if_configured() -> bool:
    """Check config and register routes on the shared HTTP server if enabled.

    The auth policy is built here, before any route is mounted, so an enabled
    endpoint without keys (and without the explicit unauthenticated opt-in)
    aborts startup instead of serving the agent openly.

    Returns:
        True if routes were registered, False otherwise.

    Raises:
        ConfigurationError: If the entrypoint is enabled but its auth
            configuration is invalid.
    """
    config = AGUIConfig(get_default_config())
    if not config.is_configured():
        logger.debug("AGUI entrypoint not enabled")
        return False

    auth = config.get_auth()
    if auth.allow_unauthenticated:
        logger.warning(
            "AG-UI entrypoint runs WITHOUT authentication "
            "(agui.server.allowUnauthenticated=true)"
        )

    from entrypoints.http_server.server import register_router

    register_router(router)
    logger.info("AG-UI entrypoint registered on shared HTTP server")
    return True
