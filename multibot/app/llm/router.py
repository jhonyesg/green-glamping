"""LLM router: selects provider per tenant, handles failover, STT routing."""

import sqlalchemy as sa
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_credentials
from app.llm.base import LLMProvider, LLMRequest, LLMResponse, STTRequest, STTResponse


def _build_provider(provider_name: str, model: str, api_key: str, base_url: str, capabilities: dict) -> LLMProvider:
    if provider_name == "minimax":
        from app.llm.minimax import MiniMaxAdapter
        return MiniMaxAdapter(api_key=api_key, model=model, base_url=base_url)
    else:
        from app.llm.openai_compat import OpenAICompatAdapter
        audio_capable = capabilities.get("audio_input", False)
        return OpenAICompatAdapter(
            api_key=api_key, model=model, base_url=base_url, audio_capable=audio_capable
        )


async def _load_providers(tenant_id: int, session: AsyncSession) -> list[LLMProvider]:
    rows = (await session.execute(
        sa.text(
            "SELECT provider_name, model, api_key, base_url, capabilities "
            "FROM llm_providers "
            "WHERE tenant_id = :tid AND is_active = true "
            "ORDER BY priority DESC"
        ),
        {"tid": tenant_id},
    )).fetchall()

    providers = []
    for row in rows:
        try:
            creds = decrypt_credentials(row.api_key) if row.api_key else {}
            api_key = creds.get("api_key", row.api_key or "")
            caps = row.capabilities or {}
            providers.append(_build_provider(
                row.provider_name, row.model, api_key, row.base_url or "", caps
            ))
        except Exception as e:
            logger.warning(f"Could not load provider {row.provider_name}: {e}")
    return providers


async def route_llm(request: LLMRequest, session: AsyncSession) -> LLMResponse:
    """Send an LLM request using the tenant's configured providers with failover."""
    providers = await _load_providers(request.tenant_id, session)
    if not providers:
        raise RuntimeError(f"No LLM providers configured for tenant {request.tenant_id}")

    last_err: Exception | None = None
    for provider in providers:
        try:
            return await provider.complete(request)
        except Exception as e:
            logger.warning(f"LLM provider {provider.provider_name} failed: {e}")
            last_err = e

    raise RuntimeError(f"All LLM providers failed: {last_err}")


async def route_stt(request: STTRequest, session: AsyncSession) -> STTResponse:
    """
    STT routing: prefer a multimodal provider that supports audio input.
    Falls back to Whisper-compatible (OpenAI STT) if available.
    """
    providers = await _load_providers(request.tenant_id, session)

    # Prefer audio-capable providers
    audio_providers = [p for p in providers if p.supports_audio()]
    ordered = audio_providers + [p for p in providers if not p.supports_audio()]

    last_err: Exception | None = None
    for provider in ordered:
        try:
            return await provider.transcribe(request)
        except NotImplementedError:
            continue
        except Exception as e:
            logger.warning(f"STT provider {provider.provider_name} failed: {e}")
            last_err = e

    raise RuntimeError(f"All STT providers failed: {last_err}")
