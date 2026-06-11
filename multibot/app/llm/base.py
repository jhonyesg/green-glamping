"""LLM provider interface and shared dataclasses."""

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMRequest:
    messages: list[LLMMessage]
    model: str = ""
    max_tokens: int = 512
    temperature: float = 0.3
    tenant_id: int = 0
    conversation_id: int | None = None


@dataclass
class LLMResponse:
    text: str
    model: str
    tokens_used: int = 0
    latency_ms: int = 0
    provider: str = ""


@dataclass
class STTRequest:
    audio_bytes: bytes
    mime_type: str = "audio/ogg"
    language: str = "es"
    tenant_id: int = 0


@dataclass
class STTResponse:
    text: str
    confidence: float = 1.0
    language: str = "es"
    latency_ms: int = 0
    provider: str = ""


@runtime_checkable
class LLMProvider(Protocol):
    """Async LLM provider interface."""

    provider_name: str

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """Send chat completion request and return response."""
        ...

    async def transcribe(self, request: STTRequest) -> STTResponse:
        """Transcribe audio to text. Raise NotImplementedError if unsupported."""
        ...

    def supports_audio(self) -> bool:
        """Return True if provider supports multimodal audio input."""
        ...
