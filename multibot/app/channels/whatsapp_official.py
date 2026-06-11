"""WhatsApp Cloud API (Meta official) adapter."""

import hashlib
import hmac
import time
from dataclasses import dataclass

import httpx
from loguru import logger

from app.channels.base import (
    ChannelAdapter,
    ContentType,
    InboundMessage,
    MessageContent,
    OutboundMessage,
    SendResult,
)

WA_API_BASE = "https://graph.facebook.com/v19.0"


class WhatsAppOfficialAdapter:
    """Meta Cloud API adapter for WhatsApp Business."""

    def __init__(self, phone_number_id: str, access_token: str, app_secret: str = ""):
        self._phone_number_id = phone_number_id
        self._access_token = access_token
        self._app_secret = app_secret

    def parse_inbound(self, payload: dict) -> InboundMessage | None:
        try:
            entry = payload["entry"][0]
            change = entry["changes"][0]["value"]
            msg = change["messages"][0]
            contact = change["contacts"][0]
        except (KeyError, IndexError):
            return None

        msg_type = msg.get("type", "text")
        thread_id = contact["wa_id"]
        push_name = contact.get("profile", {}).get("name", "")

        if msg_type == "text":
            content = MessageContent(
                type=ContentType.text,
                text=msg["text"]["body"],
            )
        elif msg_type == "audio":
            content = MessageContent(
                type=ContentType.audio,
                media_id=msg["audio"]["id"],
                mime_type=msg["audio"].get("mime_type", "audio/ogg"),
            )
        elif msg_type == "image":
            content = MessageContent(
                type=ContentType.image,
                media_id=msg["image"]["id"],
                mime_type=msg["image"].get("mime_type", "image/jpeg"),
                caption=msg["image"].get("caption", ""),
            )
        else:
            content = MessageContent(type=ContentType.text, text=f"[{msg_type}]")

        return InboundMessage(
            channel_type="whatsapp_official",
            tenant_slug="",
            external_thread_id=thread_id,
            user_external_id=thread_id,
            push_name=push_name,
            message_id=msg.get("id", ""),
            content=content,
            raw=msg,
        )

    async def send(self, message: OutboundMessage) -> SendResult:
        url = f"{WA_API_BASE}/{self._phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": message.thread_id,
            "type": "text",
            "text": {"body": message.text},
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            msg_id = data.get("messages", [{}])[0].get("id", "")
            return SendResult(success=True, message_id=msg_id)
        except Exception as e:
            logger.error(f"WhatsApp send error: {e}")
            return SendResult(success=False, error=str(e))

    async def send_template(
        self,
        to: str,
        template_name: str,
        language_code: str = "es",
        components: list | None = None,
    ) -> SendResult:
        """Send a pre-approved template (required for messages outside 24h window)."""
        url = f"{WA_API_BASE}/{self._phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": components or [],
            },
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            msg_id = data.get("messages", [{}])[0].get("id", "")
            return SendResult(success=True, message_id=msg_id)
        except Exception as e:
            logger.error(f"WhatsApp send_template error: {e}")
            return SendResult(success=False, error=str(e))

    async def send_typing(self, thread_id: str) -> None:
        # WhatsApp Business API does not support typing indicators in Cloud API
        pass

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        if not self._app_secret:
            return True
        expected = "sha256=" + hmac.new(
            self._app_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def download_media(self, media_id: str) -> bytes:
        headers = {"Authorization": f"Bearer {self._access_token}"}
        async with httpx.AsyncClient(timeout=30) as client:
            # Step 1: get media URL
            meta = await client.get(f"{WA_API_BASE}/{media_id}", headers=headers)
            meta.raise_for_status()
            url = meta.json()["url"]
            # Step 2: download
            file_resp = await client.get(url, headers=headers)
            file_resp.raise_for_status()
        return file_resp.content
