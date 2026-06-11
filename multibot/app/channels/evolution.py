"""Evolution API adapter — WhatsApp no oficial vía Evolution API (evolution-api.com).

Evolution API es un gateway open-source de WhatsApp (basado en Baileys) muy usado
en Latinoamérica. Se despliega aparte (docker) y este adaptador habla con su REST.
"""

import httpx
from loguru import logger

from app.channels.base import (
    ContentType,
    InboundMessage,
    MessageContent,
    OutboundMessage,
    SendResult,
)


class EvolutionAPIAdapter:
    """Cliente del REST de Evolution API v2."""

    channel_type = "whatsapp_evolution"

    def __init__(self, base_url: str, api_key: str, instance: str):
        self._base = base_url.rstrip("/")
        self._api_key = api_key
        self._instance = instance

    def _headers(self) -> dict:
        return {"apikey": self._api_key, "Content-Type": "application/json"}

    def parse_inbound(self, payload: dict) -> InboundMessage | None:
        """Parsea el webhook de Evolution (evento messages.upsert)."""
        if payload.get("event") not in ("messages.upsert", "MESSAGES_UPSERT"):
            return None
        data = payload.get("data") or {}
        key = data.get("key") or {}
        if key.get("fromMe"):
            return None

        msg = data.get("message") or {}
        text = (
            msg.get("conversation")
            or (msg.get("extendedTextMessage") or {}).get("text")
            or ""
        )
        jid = key.get("remoteJid", "")

        content_type = ContentType.text
        media_id = None
        if "audioMessage" in msg:
            content_type, media_id = ContentType.audio, key.get("id")
        elif "imageMessage" in msg:
            content_type, media_id = ContentType.image, key.get("id")

        return InboundMessage(
            channel_type=self.channel_type,
            tenant_slug="",
            external_thread_id=jid,
            user_external_id=jid,
            push_name=data.get("pushName", ""),
            message_id=key.get("id", ""),
            content=MessageContent(
                type=content_type,
                text=text or None,
                media_id=media_id,
                caption=(msg.get("imageMessage") or {}).get("caption"),
            ),
            raw=payload,
        )

    async def send(self, message: OutboundMessage) -> SendResult:
        number = message.thread_id.split("@")[0]
        url = f"{self._base}/message/sendText/{self._instance}"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    url,
                    headers=self._headers(),
                    json={"number": number, "text": message.text},
                )
                resp.raise_for_status()
                data = resp.json()
            return SendResult(success=True, message_id=str(data.get("key", {}).get("id", "")))
        except Exception as e:
            logger.error(f"Evolution send error: {e}")
            return SendResult(success=False, error=str(e))

    async def send_typing(self, thread_id: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(
                    f"{self._base}/chat/sendPresence/{self._instance}",
                    headers=self._headers(),
                    json={"number": thread_id.split("@")[0], "presence": "composing", "delay": 1200},
                )
        except Exception:
            pass

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        return True  # Evolution autentica por apikey en la URL del webhook

    async def get_status(self) -> dict:
        """Estado de la instancia: open (conectado), connecting, close."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{self._base}/instance/connectionState/{self._instance}",
                    headers=self._headers(),
                )
                data = resp.json()
            state = (data.get("instance") or {}).get("state", "unknown")
            return {"status": "connected" if state == "open" else state}
        except Exception as e:
            return {"status": "unreachable", "error": str(e)[:80]}

    async def get_qr(self) -> str | None:
        """Devuelve el QR (base64) para vincular el número."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self._base}/instance/connect/{self._instance}",
                    headers=self._headers(),
                )
                data = resp.json()
            return data.get("base64") or data.get("code")
        except Exception:
            return None
