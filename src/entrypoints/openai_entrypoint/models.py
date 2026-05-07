"""OpenAI-compatible request/response models for the chat completions API."""

import time
import uuid

from pydantic import BaseModel, ConfigDict, Field

# ── Request models ──────────────────────────────────────────────────────────


class ChatMessage(BaseModel):
    """Single message in the OpenAI chat format."""

    role: str  # "system", "user", "assistant"
    content: str


class ChatCompletionRequest(BaseModel):
    """POST /v1/chat/completions request body."""

    model_config = ConfigDict(extra="ignore")

    model: str = "dev-agents"
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None


# ── Response models (non-streaming) ─────────────────────────────────────────


class ChoiceMessage(BaseModel):
    role: str = "assistant"
    content: str


class UsageInfo(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class Choice(BaseModel):
    index: int = 0
    message: ChoiceMessage
    logprobs: None = None
    finish_reason: str = "stop"


class ChatCompletionResponse(BaseModel):
    """Non-streaming response matching OpenAI format."""

    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = "dev-agents"
    system_fingerprint: str | None = None
    choices: list[Choice]
    usage: UsageInfo = Field(default_factory=UsageInfo)


# ── Response models (streaming) ─────────────────────────────────────────────


class DeltaContent(BaseModel):
    """Delta object in a streaming chunk."""

    role: str | None = None
    content: str | None = None
    reasoning_content: str | None = None


class StreamChoice(BaseModel):
    index: int = 0
    delta: DeltaContent
    logprobs: None = None
    finish_reason: str | None = None


class ChatCompletionChunk(BaseModel):
    """Single SSE chunk matching OpenAI streaming format."""

    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}")
    object: str = "chat.completion.chunk"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str = "dev-agents"
    system_fingerprint: str | None = None
    choices: list[StreamChoice]


# ── Error response ──────────────────────────────────────────────────────────


class OpenAIError(BaseModel):
    """OpenAI-compatible error object."""

    message: str
    type: str = "server_error"
    code: str | None = None


class OpenAIErrorResponse(BaseModel):
    """OpenAI-compatible error response wrapper."""

    error: OpenAIError


# ── Models list response ────────────────────────────────────────────────────


class ModelInfo(BaseModel):
    id: str = "dev-agents"
    object: str = "model"
    created: int = Field(default_factory=lambda: int(time.time()))
    owned_by: str = "codeligence"


class ModelsResponse(BaseModel):
    object: str = "list"
    data: list[ModelInfo] = Field(default_factory=lambda: [ModelInfo()])
