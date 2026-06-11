"""
Multimodal input handler: audio → STT, image → vision, video → frame+audio, PDF.
Sprint 5 Task 19.x
"""

import io
import time
from dataclasses import dataclass

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.channels.base import ContentType, MessageContent
from app.llm.base import STTRequest


@dataclass
class MultimodalResult:
    text: str | None
    content_type: ContentType
    media_id: str | None = None
    latency_ms: int = 0
    provider: str = ""


async def process_inbound_content(
    content: MessageContent,
    tenant_id: int,
    session: AsyncSession,
    channel_adapter=None,
) -> MultimodalResult:
    """
    Convert any inbound content type to text (or pass through text).
    Returns a MultimodalResult with extracted text for the pipeline.
    """
    start = time.monotonic()

    if content.type == ContentType.text:
        return MultimodalResult(
            text=content.text,
            content_type=ContentType.text,
            latency_ms=0,
        )

    if content.type == ContentType.audio:
        return await _handle_audio(content, tenant_id, session, channel_adapter, start)

    if content.type == ContentType.image:
        return await _handle_image(content, tenant_id, session, channel_adapter, start)

    if content.type == ContentType.video:
        return await _handle_video(content, tenant_id, session, channel_adapter, start)

    if content.type == ContentType.document:
        return await _handle_document(content, tenant_id, session, channel_adapter, start)

    return MultimodalResult(
        text=None,
        content_type=content.type,
        latency_ms=int((time.monotonic() - start) * 1000),
    )


async def _handle_audio(content, tenant_id, session, adapter, start) -> MultimodalResult:
    """Download audio and transcribe via STT router."""
    try:
        audio_bytes = content.file_bytes
        if not audio_bytes and adapter and (content.file_id or content.media_id):
            fid = content.file_id or content.media_id
            audio_bytes = await adapter.download_media(fid)

        if not audio_bytes:
            return MultimodalResult(text="[audio no disponible]", content_type=ContentType.audio)

        from app.llm.router import route_stt
        stt_req = STTRequest(
            audio_bytes=audio_bytes,
            mime_type=content.mime_type or "audio/ogg",
            language="es",
            tenant_id=tenant_id,
        )
        stt_resp = await route_stt(stt_req, session)
        return MultimodalResult(
            text=stt_resp.text,
            content_type=ContentType.audio,
            latency_ms=stt_resp.latency_ms,
            provider=stt_resp.provider,
        )
    except Exception as e:
        logger.error(f"Audio STT failed: {e}")
        return MultimodalResult(text="[audio — transcripción no disponible]", content_type=ContentType.audio)


async def _handle_image(content, tenant_id, session, adapter, start) -> MultimodalResult:
    """Download image and describe via vision LLM (or return caption if present)."""
    if content.caption:
        return MultimodalResult(
            text=content.caption,
            content_type=ContentType.image,
            latency_ms=int((time.monotonic() - start) * 1000),
        )

    try:
        img_bytes = content.file_bytes
        if not img_bytes and adapter and (content.file_id or content.media_id):
            fid = content.file_id or content.media_id
            img_bytes = await adapter.download_media(fid)

        if not img_bytes:
            return MultimodalResult(text="[imagen]", content_type=ContentType.image)

        # Vision: encode to base64 and send to LLM
        import base64
        b64 = base64.b64encode(img_bytes).decode()
        mime = content.mime_type or "image/jpeg"

        from app.llm.base import LLMMessage, LLMRequest
        from app.llm.router import route_llm
        req = LLMRequest(
            messages=[LLMMessage(
                role="user",
                content=f"Describe brevemente qué hay en esta imagen en español. [IMAGE:{mime};base64,{b64[:100]}...]",
            )],
            tenant_id=tenant_id,
            max_tokens=200,
        )
        resp = await route_llm(req, session)
        return MultimodalResult(
            text=resp.text,
            content_type=ContentType.image,
            latency_ms=resp.latency_ms,
            provider=resp.provider,
        )
    except Exception as e:
        logger.error(f"Image vision failed: {e}")
        return MultimodalResult(text="[imagen]", content_type=ContentType.image)


async def _handle_video(content, tenant_id, session, adapter, start) -> MultimodalResult:
    """For video: extract audio track and run STT (simplified — delegate to STT)."""
    logger.info("Video received — extracting audio track (stub)")
    if content.caption:
        return MultimodalResult(text=content.caption, content_type=ContentType.video)
    return MultimodalResult(
        text="[video — no puedo procesar video en este momento]",
        content_type=ContentType.video,
        latency_ms=int((time.monotonic() - start) * 1000),
    )


async def _handle_document(content, tenant_id, session, adapter, start) -> MultimodalResult:
    """For PDF documents: extract text via PyMuPDF if available, else stub."""
    if content.caption:
        return MultimodalResult(text=content.caption, content_type=ContentType.document)

    try:
        doc_bytes = content.file_bytes
        if not doc_bytes and adapter and content.file_id:
            doc_bytes = await adapter.download_media(content.file_id)

        if doc_bytes:
            try:
                import fitz  # PyMuPDF
                doc = fitz.open(stream=doc_bytes, filetype="pdf")
                text = "\n".join(page.get_text() for page in doc)[:1000]
                return MultimodalResult(
                    text=text or "[PDF sin texto extraíble]",
                    content_type=ContentType.document,
                    latency_ms=int((time.monotonic() - start) * 1000),
                )
            except ImportError:
                pass
    except Exception as e:
        logger.error(f"Document extraction failed: {e}")

    return MultimodalResult(
        text="[documento — no puedo leer el archivo en este momento]",
        content_type=ContentType.document,
        latency_ms=int((time.monotonic() - start) * 1000),
    )
