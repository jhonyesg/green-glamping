"""Python adapter that talks to the Node.js Baileys bridge microservice."""

import httpx
from loguru import logger

from app.channels.base import (
    ContentType,
    InboundMessage,
    MessageContent,
    OutboundMessage,
    SendResult,
)


class WhatsAppUnofficialAdapter:
    """Delegates to the Node.js Baileys bridge at `bridge_url`."""

    def __init__(self, bridge_url: str = "http://localhost:3001"):
        self._bridge = bridge_url.rstrip("/")

    def parse_inbound(self, payload: dict) -> InboundMessage:
        """Parse a forwarded message from the bridge's POST callback."""
        jid = payload.get("jid", "")
        text = payload.get("text", "")
        push_name = payload.get("pushName", "")
        msg_id = payload.get("id", "")

        content = MessageContent(type=ContentType.text, text=text or None)
        return InboundMessage(
            channel_type="whatsapp_unofficial",
            tenant_slug="",
            external_thread_id=jid,
            user_external_id=jid,
            push_name=push_name,
            message_id=msg_id,
            content=content,
            raw=payload,
        )

    async def send(self, message: OutboundMessage) -> SendResult:
        url = f"{self._bridge}/send"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json={"to": message.thread_id, "text": message.text})
                resp.raise_for_status()
            return SendResult(success=True)
        except Exception as e:
            logger.error(f"WhatsApp unofficial send error: {e}")
            return SendResult(success=False, error=str(e))

    async def send_typing(self, thread_id: str) -> None:
        # Bridge doesn't support typing indicators yet
        pass

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        return True  # bridge is internal; no signature needed

    async def get_status(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self._bridge}/status")
                return resp.json()
        except Exception:
            return {"status": "unreachable"}
