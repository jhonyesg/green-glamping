"""OpenAI-compatible adapter: works with OpenAI, Groq, Together, Ollama, etc."""

import time

import httpx
from loguru import logger

from app.llm.base import LLMProvider, LLMRequest, LLMResponse, STTRequest, STTResponse

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_STT_URL = "https://api.openai.com/v1/audio/transcriptions"


class OpenAICompatAdapter:
    provider_name = "openai_compat"

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "",
        stt_model: str = "whisper-1",
        audio_capable: bool = False,
    ):
        self._api_key = api_key
        self._model = model
        self._stt_model = stt_model
        self._audio_capable = audio_capable
        chat_base = base_url.rstrip("/") if base_url else "https://api.openai.com/v1"
        self._chat_url = f"{chat_base}/chat/completions"
        self._stt_url = f"{chat_base}/audio/transcriptions"

    def supports_audio(self) -> bool:
        return self._audio_capable

    async def complete(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self._model
        payload = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(self._chat_url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.error(f"OpenAICompat complete error: {e}")
            raise

        elapsed = int((time.monotonic() - start) * 1000)
        choice = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return LLMResponse(
            text=choice,
            model=model,
            tokens_used=usage.get("total_tokens", 0),
            latency_ms=elapsed,
            provider=self.provider_name,
        )

    async def transcribe(self, request: STTRequest) -> STTResponse:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    self._stt_url,
                    headers=headers,
                    files={"file": ("audio.ogg", request.audio_bytes, request.mime_type)},
                    data={"model": self._stt_model, "language": request.language},
                )
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.error(f"OpenAICompat STT error: {e}")
            raise

        elapsed = int((time.monotonic() - start) * 1000)
        return STTResponse(
            text=data.get("text", ""),
            latency_ms=elapsed,
            provider=self.provider_name,
        )
