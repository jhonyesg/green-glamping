"""MiniMax LLM adapter (HTTP client to MiniMax API).

Soporta la plataforma nueva (api.minimax.io — compatible OpenAI) y la
legada (api.minimax.chat). Si no hay base_url configurada, prueba los
endpoints en orden hasta que uno responda.
"""

import time

import httpx
from loguru import logger

from app.llm.base import LLMRequest, LLMResponse, STTRequest, STTResponse

# Candidatos en orden: plataforma nueva primero (cuentas recientes / modelos M*)
CHAT_URL_CANDIDATES = [
    "https://api.minimax.io/v1/chat/completions",
    "https://api.minimaxi.com/v1/chat/completions",
    "https://api.minimax.chat/v1/text/chatcompletion_v2",
]
MINIMAX_STT_URL = "https://api.minimax.io/v1/audio/transcriptions"
MINIMAX_STT_LEGACY = "https://api.minimax.chat/v1/speech_to_text"


def _extract_error(data: dict) -> str:
    """MiniMax reporta errores en base_resp aunque el HTTP sea 200."""
    base = data.get("base_resp") or {}
    if base.get("status_code") not in (None, 0):
        return f"MiniMax error {base.get('status_code')}: {base.get('status_msg', '')}"
    if "error" in data:
        err = data["error"]
        return err.get("message", str(err)) if isinstance(err, dict) else str(err)
    return "respuesta sin 'choices'"


class MiniMaxAdapter:
    provider_name = "minimax"

    def __init__(self, api_key: str, model: str = "abab6.5-chat", base_url: str = ""):
        self._api_key = api_key
        self._model = model
        if base_url:
            b = base_url.rstrip("/")
            if "chatcompletion" in b or b.endswith("/chat/completions"):
                self._chat_urls = [b]
            else:
                self._chat_urls = [b + "/chat/completions"]
        else:
            self._chat_urls = CHAT_URL_CANDIDATES

    def supports_audio(self) -> bool:
        return True

    async def complete(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self._model
        # Construir messages: si el request viene con
        # system+user_prompt, armar messages. Si viene con messages, usarlos.
        if request.messages:
            messages = [{"role": m.role, "content": m.content} for m in request.messages]
        else:
            messages = []
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            if request.user_prompt:
                messages.append({"role": "user", "content": request.user_prompt})
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        last_error = ""
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=30) as client:
            for url in self._chat_urls:
                try:
                    resp = await client.post(url, json=payload, headers=headers)
                    data = resp.json()
                except Exception as e:
                    last_error = f"{url}: {e}"
                    logger.warning(f"MiniMax endpoint falló ({last_error})")
                    continue

                choices = data.get("choices")
                if resp.status_code == 200 and choices:
                    elapsed = int((time.monotonic() - start) * 1000)
                    usage = data.get("usage", {})
                    text = choices[0]["message"]["content"]
                    # Modelos razonadores (M1/M2/M3) emiten <think>...</think> — nunca mostrarlo al cliente
                    import re
                    text = re.sub(r"<think>.*?(</think>|$)", "", text, flags=re.DOTALL).strip()
                    return LLMResponse(
                        text=text,
                        model=model,
                        tokens_used=usage.get("total_tokens", 0),
                        latency_ms=elapsed,
                        provider=self.provider_name,
                    )

                last_error = f"{url}: HTTP {resp.status_code} — {_extract_error(data)}"
                logger.warning(f"MiniMax endpoint sin choices ({last_error})")

        raise RuntimeError(f"MiniMax no respondió en ningún endpoint. Último error: {last_error}")

    async def transcribe(self, request: STTRequest) -> STTResponse:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        start = time.monotonic()
        last_error = ""

        async with httpx.AsyncClient(timeout=60) as client:
            for url in (MINIMAX_STT_URL, MINIMAX_STT_LEGACY):
                try:
                    resp = await client.post(
                        url,
                        headers=headers,
                        files={"file": ("audio.ogg", request.audio_bytes, request.mime_type)},
                        data={"model": "speech-01", "language": request.language},
                    )
                    data = resp.json()
                except Exception as e:
                    last_error = f"{url}: {e}"
                    continue

                text = data.get("text", "")
                if resp.status_code == 200 and text:
                    elapsed = int((time.monotonic() - start) * 1000)
                    return STTResponse(
                        text=text,
                        confidence=data.get("confidence", 1.0),
                        language=request.language,
                        latency_ms=elapsed,
                        provider=self.provider_name,
                    )
                last_error = f"{url}: HTTP {resp.status_code} — {_extract_error(data)}"

        raise RuntimeError(f"MiniMax STT falló. Último error: {last_error}")
