"""Normalized channel adapter interface and message dataclasses."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable


class ContentType(StrEnum):
    text = "text"
    audio = "audio"
    image = "image"
    video = "video"
    document = "document"
    mixed = "mixed"


@dataclass
class MessageContent:
    type: ContentType
    text: str | None = None
    file_id: str | None = None   # Telegram file_id
    media_id: str | None = None  # WhatsApp media_id
    file_bytes: bytes | None = None
    mime_type: str | None = None
    caption: str | None = None


@dataclass
class InboundMessage:
    channel_type: str
    tenant_slug: str
    external_thread_id: str      # chat_id, phone number, etc.
    user_external_id: str
    push_name: str | None        # display name from channel
    message_id: str
    content: MessageContent
    raw: dict = field(default_factory=dict)  # original payload for debugging


@dataclass
class SendResult:
    success: bool
    message_id: str | None = None
    error: str | None = None


@dataclass
class OutboundMessage:
    thread_id: str
    text: str | None = None
    file_id: str | None = None
    file_bytes: bytes | None = None
    content_type: ContentType = ContentType.text
    caption: str | None = None


@runtime_checkable
class ChannelAdapter(Protocol):
    channel_type: str

    def parse_inbound(self, payload: dict) -> InboundMessage:
        ...

    async def send(self, message: OutboundMessage) -> SendResult:
        ...

    async def send_typing(self, thread_id: str) -> None:
        ...

    def verify_webhook(self, payload: bytes, signature: str) -> bool:
        ...
