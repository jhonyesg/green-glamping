"""TTS generation: sha256-cached audio files per tenant, with voice variant rotation."""

import hashlib
import time
from pathlib import Path

import httpx
import sqlalchemy as sa
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

MEDIA_ROOT = Path("media")
TTS_SUBDIR = "tts"
AUTO_PREGENERATE_THRESHOLD = 5  # promote after 5 uses

# MiniMax TTS endpoint
MINIMAX_TTS_URL = "https://api.minimax.chat/v1/text_to_speech"


def _tts_cache_key(text: str, voice_id: str) -> str:
    return hashlib.sha256(f"{voice_id}:{text}".encode()).hexdigest()


def _tts_path(tenant_slug: str, cache_key: str) -> Path:
    return MEDIA_ROOT / tenant_slug / TTS_SUBDIR / f"{cache_key}.ogg"


async def _fetch_tts(text: str, voice_id: str, api_key: str) -> bytes:
    """Call MiniMax TTS API and return OGG audio bytes."""
    payload = {
        "model": "speech-01",
        "text": text,
        "voice_id": voice_id,
        "audio_setting": {"format": "ogg", "sample_rate": 16000, "bitrate": 128000},
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(MINIMAX_TTS_URL, json=payload, headers=headers)
        resp.raise_for_status()
        return resp.content


async def get_or_generate_tts(
    text: str,
    tenant_id: int,
    tenant_slug: str,
    session: AsyncSession,
) -> bytes | None:
    """
    Return cached OGG bytes for `text`, generating via TTS if not cached.
    Returns None if no TTS provider is configured.
    """
    # Load tenant TTS config from llm_providers with capabilities.tts = true
    row = (await session.execute(
        sa.text(
            "SELECT provider_name, model, api_key, capabilities "
            "FROM llm_providers "
            "WHERE tenant_id=:tid AND is_active=true "
            "AND (capabilities->>'tts')::boolean = true "
            "ORDER BY priority DESC LIMIT 1"
        ),
        {"tid": tenant_id},
    )).fetchone()

    if not row:
        return None

    from app.core.security import decrypt_credentials
    creds = decrypt_credentials(row.api_key) if row.api_key else {}
    api_key = creds.get("api_key", row.api_key or "")

    # Pick voice variant via round-robin on media_assets
    caps = row.capabilities or {}
    voice_ids: list[str] = caps.get("voice_ids", [caps.get("voice_id", "female-shaxi-1")])
    voice_id = _pick_voice(voice_ids)

    cache_key = _tts_cache_key(text, voice_id)
    file_path = _tts_path(tenant_slug, cache_key)

    # Check DB cache first
    asset_row = (await session.execute(
        sa.text(
            "SELECT id, file_path, use_count, is_pregenerated FROM media_assets "
            "WHERE tenant_id=:tid AND file_path=:fp LIMIT 1"
        ),
        {"tid": tenant_id, "fp": str(file_path)},
    )).fetchone()

    if asset_row and file_path.exists():
        audio_bytes = file_path.read_bytes()
        await _increment_use_count(asset_row.id, asset_row.use_count, tenant_id, session)
        return audio_bytes

    # Generate via TTS provider
    try:
        start = time.monotonic()
        audio_bytes = await _fetch_tts(text, voice_id, api_key)
        elapsed = int((time.monotonic() - start) * 1000)
        logger.info(f"TTS generated {len(audio_bytes)} bytes in {elapsed}ms (voice={voice_id})")
    except Exception as e:
        logger.error(f"TTS generation failed: {e}")
        return None

    # Persist to disk
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(audio_bytes)

    # Insert cache record
    await session.execute(
        sa.text(
            "INSERT INTO media_assets "
            "(tenant_id, asset_type, file_path, mime_type, size_bytes, use_count) "
            "VALUES (:tid, 'tts_cache', :fp, 'audio/ogg', :sz, 1)"
        ),
        {"tid": tenant_id, "fp": str(file_path), "sz": len(audio_bytes)},
    )
    await session.commit()
    return audio_bytes


async def _increment_use_count(asset_id: int, current: int, tenant_id: int, session: AsyncSession):
    new_count = current + 1
    is_pregen = new_count >= AUTO_PREGENERATE_THRESHOLD
    await session.execute(
        sa.text(
            "UPDATE media_assets SET use_count=:c, is_pregenerated=:pg WHERE id=:id"
        ),
        {"c": new_count, "pg": is_pregen, "id": asset_id},
    )
    await session.commit()


def _pick_voice(voice_ids: list[str]) -> str:
    """Simple round-robin via modulo on a monotonic counter (process-scoped)."""
    import threading
    with _voice_lock:
        idx = _voice_counter[0] % len(voice_ids)
        _voice_counter[0] += 1
    return voice_ids[idx]


_voice_counter = [0]
_voice_lock = __import__("threading").Lock()
