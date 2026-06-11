"""Telegram channel adapter using python-telegram-bot v20+."""

import hashlib
import hmac
import re
from typing import Any

import httpx
from telegram import Bot, Update
from telegram.constants import ChatAction

_TOKEN_SHAPE = re.compile(r"^\d{6,12}:[A-Za-z0-9_-]{30,}$")


def token_shape_problem(token: str) -> str | None:
    """Devuelve un mensaje pedagógico si el token no tiene forma válida, o None."""
    t = token.strip()
    if not t:
        return None
    if t.startswith("@"):
        return (
            "Eso es el *nombre* del bot (lo que compartes con la gente), "
            "no el token. El token es la llave secreta que te dio @BotFather "
            "y se ve como `123456789:AAH...`"
        )
    if not _TOKEN_SHAPE.match(t):
        return (
            "Ese valor no tiene la forma de un token de Telegram "
            "(`números:letras`, ej. `123456789:AAH...`). "
            "Cópialo completo desde @BotFather."
        )
    return None

from app.channels.base import (
    ChannelAdapter,
    ContentType,
    InboundMessage,
    MessageContent,
    OutboundMessage,
    SendResult,
)


class TelegramAdapter:
    channel_type = "telegram"

    def __init__(self, bot_token: str, secret_token: str = "") -> None:
        self._bot = Bot(token=bot_token)
        self._secret_token = secret_token
        self._token = bot_token

    def parse_inbound(self, payload: dict) -> InboundMessage:
        update = Update.de_json(payload, self._bot)

        message = update.message or update.edited_message
        if message is None:
            raise ValueError("No message in Telegram update")

        chat = message.chat
        user = message.from_user
        thread_id = str(chat.id)
        user_id = str(user.id) if user else thread_id
        push_name = (
            f"{user.first_name or ''} {user.last_name or ''}".strip()
            if user else None
        )

        # Determine content type
        if message.text:
            content = MessageContent(type=ContentType.text, text=message.text)
        elif message.voice:
            content = MessageContent(
                type=ContentType.audio,
                file_id=message.voice.file_id,
                mime_type="audio/ogg",
            )
        elif message.audio:
            content = MessageContent(
                type=ContentType.audio,
                file_id=message.audio.file_id,
                mime_type=message.audio.mime_type,
            )
        elif message.photo:
            largest = max(message.photo, key=lambda p: p.file_size or 0)
            content = MessageContent(
                type=ContentType.image,
                file_id=largest.file_id,
                caption=message.caption,
            )
        elif message.video:
            content = MessageContent(
                type=ContentType.video,
                file_id=message.video.file_id,
                mime_type=message.video.mime_type,
                caption=message.caption,
            )
        elif message.document:
            content = MessageContent(
                type=ContentType.document,
                file_id=message.document.file_id,
                mime_type=message.document.mime_type,
            )
        else:
            content = MessageContent(type=ContentType.text, text="[unsupported message type]")

        return InboundMessage(
            channel_type=self.channel_type,
            tenant_slug="",  # filled by webhook handler
            external_thread_id=thread_id,
            user_external_id=user_id,
            push_name=push_name,
            message_id=str(message.message_id),
            content=content,
            raw=payload,
        )

    async def send(self, message: OutboundMessage) -> SendResult:
        try:
            async with self._bot:
                if message.content_type == ContentType.text and message.text:
                    sent = await self._bot.send_message(
                        chat_id=message.thread_id,
                        text=message.text,
                        parse_mode="Markdown",
                    )
                elif message.content_type == ContentType.image and message.file_id:
                    sent = await self._bot.send_photo(
                        chat_id=message.thread_id,
                        photo=message.file_id,
                        caption=message.caption,
                    )
                elif message.content_type == ContentType.audio and message.file_id:
                    sent = await self._bot.send_audio(
                        chat_id=message.thread_id,
                        audio=message.file_id,
                        caption=message.caption,
                    )
                else:
                    sent = await self._bot.send_message(
                        chat_id=message.thread_id,
                        text=message.text or "[empty message]",
                    )
            return SendResult(success=True, message_id=str(sent.message_id))
        except Exception as exc:
            return SendResult(success=False, error=str(exc))

    async def send_typing(self, thread_id: str) -> None:
        try:
            async with self._bot:
                await self._bot.send_chat_action(
                    chat_id=thread_id, action=ChatAction.TYPING
                )
        except Exception:
            pass

    async def download_media(self, file_id: str) -> bytes:
        async with self._bot:
            tg_file = await self._bot.get_file(file_id)
            async with httpx.AsyncClient() as client:
                resp = await client.get(tg_file.file_path)
                resp.raise_for_status()
                return resp.content

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        if not self._secret_token:
            return True
        expected = hmac.new(
            self._secret_token.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    # ── Verificación / gestión de transporte (API directa) ──

    async def _api(self, method: str, **params) -> dict:
        url = f"https://api.telegram.org/bot{self._token}/{method}"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=params) if params else await client.get(url)
            return resp.json()

    async def get_me(self) -> dict:
        """{'ok': bool, 'username': ..., 'first_name': ...} o {'ok': False, 'error': ...}"""
        data = await self._api("getMe")
        if data.get("ok"):
            r = data["result"]
            return {"ok": True, "username": r.get("username"), "first_name": r.get("first_name")}
        return {"ok": False, "error": data.get("description", "token inválido")}

    async def get_webhook_info(self) -> dict:
        data = await self._api("getWebhookInfo")
        if data.get("ok"):
            r = data["result"]
            return {
                "ok": True,
                "url": r.get("url", ""),
                "pending": r.get("pending_update_count", 0),
                "last_error": r.get("last_error_message", ""),
            }
        return {"ok": False, "error": data.get("description", "")}

    async def set_webhook(self, url: str, secret_token: str = "") -> dict:
        params: dict = {"url": url}
        if secret_token:
            params["secret_token"] = secret_token
        return await self._api("setWebhook", **params)

    async def delete_webhook(self, drop_pending: bool = False) -> dict:
        return await self._api("deleteWebhook", drop_pending_updates=drop_pending)

    async def get_updates(self, offset: int = 0, timeout: int = 25) -> dict:
        return await self._api("getUpdates", offset=offset, timeout=timeout)
