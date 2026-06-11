"""
Payment proof detection via vision LLM (Task 18.5).
Called when user sends an image and conversation is in ready_for_payment state.
"""

import base64

import sqlalchemy as sa
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

PROOF_SYSTEM_PROMPT = (
    "Eres un asistente que verifica comprobantes de pago. "
    "El usuario ha enviado una imagen. Determina si es un comprobante de transferencia bancaria, "
    "Nequi, Daviplata, o depósito bancario. "
    "Responde SOLO con JSON: {\"is_proof\": true/false, \"amount\": <number o null>, \"bank\": \"<nombre o null>\"}"
)


async def detect_payment_proof(
    image_bytes: bytes,
    mime_type: str,
    tenant_id: int,
    session: AsyncSession,
) -> dict:
    """
    Send image to vision LLM and determine if it's a payment proof.
    Returns {"is_proof": bool, "amount": float|None, "bank": str|None}.
    """
    b64 = base64.b64encode(image_bytes).decode()

    try:
        from app.llm.base import LLMMessage, LLMRequest
        from app.llm.router import route_llm
        import json

        req = LLMRequest(
            messages=[
                LLMMessage(role="system", content=PROOF_SYSTEM_PROMPT),
                LLMMessage(
                    role="user",
                    content=f"[IMAGE:{mime_type};base64,{b64}]",
                ),
            ],
            tenant_id=tenant_id,
            max_tokens=150,
            temperature=0.0,
        )
        resp = await route_llm(req, session)
        result = json.loads(resp.text.strip())
        return result
    except Exception as e:
        logger.error(f"Payment proof detection failed: {e}")
        return {"is_proof": False, "amount": None, "bank": None}


async def update_reservation_proof(
    conversation_id: int,
    proof_path: str,
    session: AsyncSession,
) -> None:
    """Record the payment proof path and advance reservation state to awaiting_proof."""
    await session.execute(
        sa.text(
            "UPDATE reservations SET payment_proof_path=:path, state='awaiting_proof', "
            "updated_at=NOW() WHERE conversation_id=:cid AND state IN ('tentative', 'ready_for_payment')"
        ),
        {"path": proof_path, "cid": conversation_id},
    )
    await session.commit()
