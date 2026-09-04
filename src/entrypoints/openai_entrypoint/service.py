"""OpenAI-compatible chat completions entrypoint.

Exposes POST /v1/chat/completions and GET /v1/models on the shared HTTP server.
Each entrypoint decides for itself whether to register (loose coupling).
"""

from collections.abc import AsyncGenerator
from typing import Any, cast
import asyncio
import time
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from agents.agents.gitchatbot.agent import AGENT_NAME
from core.config import BaseConfig, get_default_config
from core.log import get_logger, reset_context_token, set_context_token
from core.prompts import get_default_prompts
from entrypoints.http_server.auth import ApiKeyAuth
from entrypoints.openai_entrypoint.agent_context import OpenAIAgentContext
from entrypoints.openai_entrypoint.message import (
    convert_openai_messages_to_message_list,
)
from entrypoints.openai_entrypoint.models import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    Choice,
    ChoiceMessage,
    DeltaContent,
    ModelInfo,
    ModelsResponse,
    OpenAIError,
    OpenAIErrorResponse,
    StreamChoice,
)
from entrypoints.shared.agent_setup import ensure_agents_registered

logger = get_logger("OpenAIEntrypoint", level="INFO")

# Router — mounted on the shared HTTP app
router = APIRouter()

# Keepalive interval in seconds — send SSE comment while agent works
KEEPALIVE_INTERVAL = 15


class OpenAIConfig:
    """Configuration for OpenAI-compatible entrypoint."""

    def __init__(self, base_config: BaseConfig) -> None:
        self._base_config = base_config

    def get_default_timeout(self) -> int:
        return int(self._base_config.get_value("openai.agent.defaultTimeout", 300))

    def get_default_agent_type(self) -> str:
        return cast(
            "str",
            self._base_config.get_value("openai.agent.defaultAgentType", AGENT_NAME),
        )

    def is_configured(self) -> bool:
        """Check if OpenAI entrypoint is enabled."""
        return self._base_config.get_bool("openai.server.enabled", False)

    def get_model_name(self) -> str:
        """Model name advertised by /v1/models and echoed in responses."""
        return cast(
            "str",
            self._base_config.get_value("openai.server.modelName", "dev-agents"),
        )

    def is_streaming_enabled(self) -> bool:
        """Whether SSE streaming is allowed. When false, stream requests fall back to a single JSON response."""
        return self._base_config.get_bool("openai.server.streaming", True)

    def is_thinking_enabled(self) -> bool:
        """Whether agent status updates are emitted as reasoning_content chunks."""
        return self._base_config.get_bool("openai.server.thinking", True)

    def get_auth(self) -> ApiKeyAuth:
        """Validated Bearer-token policy for the ``/v1`` routes.

        Raises:
            ConfigurationError: If ``openai.server.apiKeys`` is malformed or
                empty without ``openai.server.allowUnauthenticated``.
        """
        return ApiKeyAuth.from_config(self._base_config, "openai")


def _check_auth(request: Request, config: OpenAIConfig) -> None:
    """Reject the request with 401 unless it satisfies the configured auth policy."""
    if not config.get_auth().is_authorized(request.headers.get("authorization", "")):
        _raise_error(401, "Invalid API key", error_type="invalid_request_error")


def _raise_error(
    status_code: int,
    message: str,
    error_type: str = "server_error",
    code: str | None = None,
) -> None:
    """Raise an OpenAI-formatted JSON error response."""
    from fastapi import HTTPException

    raise HTTPException(
        status_code=status_code,
        detail=OpenAIErrorResponse(
            error=OpenAIError(message=message, type=error_type, code=code)
        ).model_dump(),
    )


def _make_content_chunk(completion_id: str, created: int, model: str, text: str) -> str:
    """Build an SSE data line for a content chunk."""
    chunk = ChatCompletionChunk(
        id=completion_id,
        created=created,
        model=model,
        choices=[StreamChoice(delta=DeltaContent(content=text))],
    )
    return f"data: {chunk.model_dump_json(exclude_none=True)}\n\n"


def _make_reasoning_chunk(
    completion_id: str, created: int, model: str, text: str
) -> str:
    """Build an SSE data line for a reasoning_content chunk (DeepSeek-style)."""
    chunk = ChatCompletionChunk(
        id=completion_id,
        created=created,
        model=model,
        choices=[StreamChoice(delta=DeltaContent(reasoning_content=text))],
    )
    return f"data: {chunk.model_dump_json(exclude_none=True)}\n\n"


def _make_finish_chunk(completion_id: str, created: int, model: str) -> str:
    """Build the final SSE data line with finish_reason (empty delta, per spec)."""
    chunk = ChatCompletionChunk(
        id=completion_id,
        created=created,
        model=model,
        choices=[StreamChoice(delta=DeltaContent(), finish_reason="stop")],
    )
    return f"data: {chunk.model_dump_json(exclude_none=True)}\n\n"


# ── GET /v1/models ──────────────────────────────────────────────────────────


@router.get("/v1/models")
async def list_models(request: Request) -> ModelsResponse:
    """List available models. Returns the single configured model."""
    config = OpenAIConfig(get_default_config())
    _check_auth(request, config)
    return ModelsResponse(data=[ModelInfo(id=config.get_model_name())])


# ── POST /v1/chat/completions ───────────────────────────────────────────────


@router.post("/v1/chat/completions")
async def chat_completions(body: ChatCompletionRequest, request: Request) -> Any:
    """OpenAI-compatible chat completions endpoint.

    Supports both streaming (SSE) and non-streaming modes.
    """
    base_config = get_default_config()
    config = OpenAIConfig(base_config)
    _check_auth(request, config)

    if not body.messages:
        _raise_error(
            400, "At least one message is required", error_type="invalid_request_error"
        )

    if body.stream and config.is_streaming_enabled():
        return StreamingResponse(
            _stream_response(body, config, base_config),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        if body.stream:
            logger.info(
                "Streaming requested but disabled by config — falling back to non-streaming response"
            )
        return await _non_stream_response(body, config, base_config)


# ── Non-streaming handler ──────────────────────────────────────────────────


async def _non_stream_response(
    body: ChatCompletionRequest, config: OpenAIConfig, base_config: BaseConfig
) -> JSONResponse:
    """Run agent, collect full response, return as single JSON."""
    thread_id = str(uuid.uuid4())
    context_token = set_context_token(thread_id)

    try:
        message_list = convert_openai_messages_to_message_list(body.messages, thread_id)

        context = OpenAIAgentContext(
            message_list=message_list,
            config=base_config,
            prompts=get_default_prompts(),
            thread_id=thread_id,
            streaming=False,
        )

        agent_type = config.get_default_agent_type()
        timeout = config.get_default_timeout()
        agent_service = ensure_agents_registered()

        logger.info(f"Non-streaming request: agent={agent_type}, timeout={timeout}s")

        await agent_service.execute_agent_by_type(
            agent_type=agent_type, context=context, timeout_seconds=timeout
        )

        response_text = context.get_full_response()

        result = ChatCompletionResponse(
            model=body.model,
            choices=[
                Choice(message=ChoiceMessage(content=response_text)),
            ],
        )

        return JSONResponse(content=result.model_dump())

    except Exception as e:
        logger.error(f"Non-streaming request failed: {e}")
        error_body = OpenAIErrorResponse(
            error=OpenAIError(message="Agent execution failed", type="server_error")
        )
        return JSONResponse(status_code=500, content=error_body.model_dump())
    finally:
        reset_context_token(context_token)


# ── Streaming handler ──────────────────────────────────────────────────────


async def _stream_response(
    body: ChatCompletionRequest, config: OpenAIConfig, base_config: BaseConfig
) -> AsyncGenerator[str, None]:
    """Run agent, stream SSE chunks. Sends keepalive comments while agent works."""
    thread_id = str(uuid.uuid4())
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created = int(time.time())
    context_token = set_context_token(thread_id)

    try:
        message_list = convert_openai_messages_to_message_list(body.messages, thread_id)
        event_queue: asyncio.Queue[Any] = asyncio.Queue()

        context = OpenAIAgentContext(
            message_list=message_list,
            config=base_config,
            prompts=get_default_prompts(),
            thread_id=thread_id,
            streaming=True,
            event_queue=event_queue,
        )

        agent_type = config.get_default_agent_type()
        timeout = config.get_default_timeout()
        thinking_enabled = config.is_thinking_enabled()
        agent_service = ensure_agents_registered()

        logger.info(
            f"Streaming request: agent={agent_type}, timeout={timeout}s, "
            f"thinking={thinking_enabled}"
        )

        # Send initial role chunk (spec requires content: "" alongside role)
        initial_chunk = ChatCompletionChunk(
            id=completion_id,
            created=created,
            model=body.model,
            choices=[StreamChoice(delta=DeltaContent(role="assistant", content=""))],
        )
        yield f"data: {initial_chunk.model_dump_json()}\n\n"

        # Start agent execution as background task
        agent_task = asyncio.create_task(
            agent_service.execute_agent_by_type(
                agent_type=agent_type, context=context, timeout_seconds=timeout
            )
        )

        # Stream events from queue with keepalive
        last_keepalive = time.monotonic()

        while not agent_task.done():
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=0.1)

                if event["type"] == "content":
                    yield _make_content_chunk(
                        completion_id, created, body.model, event["text"]
                    )
                    last_keepalive = time.monotonic()

                elif event["type"] == "status" and thinking_enabled:
                    yield _make_reasoning_chunk(
                        completion_id,
                        created,
                        body.model,
                        event["message"] + "\n",
                    )
                    last_keepalive = time.monotonic()

            except TimeoutError:
                now = time.monotonic()
                if now - last_keepalive >= KEEPALIVE_INTERVAL:
                    yield ": keepalive\n\n"
                    last_keepalive = now

        # Drain remaining events
        while not event_queue.empty():
            try:
                event = event_queue.get_nowait()
                if event["type"] == "content":
                    yield _make_content_chunk(
                        completion_id, created, body.model, event["text"]
                    )
            except asyncio.QueueEmpty:
                break

        # Check for agent errors
        try:
            await agent_task
        except Exception as e:
            logger.error(f"Agent execution failed during stream: {e}")
            # Error as content chunk, then separate finish chunk (per spec)
            yield _make_content_chunk(
                completion_id,
                created,
                body.model,
                "\n\n[Error: agent execution failed]",
            )
            yield _make_finish_chunk(completion_id, created, body.model)
            yield "data: [DONE]\n\n"
            return

        # Send finish chunk (empty delta + finish_reason, per spec)
        yield _make_finish_chunk(completion_id, created, body.model)
        yield "data: [DONE]\n\n"

        logger.info(f"Streaming response completed: {completion_id}")

    except Exception as e:
        logger.error(f"Streaming request failed: {e}")
        yield _make_content_chunk(
            completion_id, created, body.model, "\n\n[Error: agent execution failed]"
        )
        yield _make_finish_chunk(completion_id, created, body.model)
        yield "data: [DONE]\n\n"
    finally:
        reset_context_token(context_token)


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
    config = OpenAIConfig(get_default_config())
    if not config.is_configured():
        logger.debug("OpenAI entrypoint not enabled")
        return False

    auth = config.get_auth()
    if auth.allow_unauthenticated:
        logger.warning(
            "OpenAI-compatible entrypoint runs WITHOUT authentication "
            "(openai.server.allowUnauthenticated=true)"
        )

    from entrypoints.http_server.server import register_router

    register_router(router)
    logger.info("OpenAI-compatible entrypoint registered on shared HTTP server")
    return True
