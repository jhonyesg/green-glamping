"""Send handoff notification to the human operator via Telegram."""

from loguru import logger


async def notify_human(
    conversation: dict,
    rule_code: str,
    user_message: str,
    recent_turns: list[dict],
    notify_channel: str,
    notify_target: str,
    bot_token: str,
) -> None:
    """
    Send a Telegram message to the human operator with conversation context.
    notify_channel: "telegram"
    notify_target: chat_id of the human (e.g. Johana's Telegram ID)
    """
    if not notify_target or not bot_token:
        logger.warning(f"No notify_target configured for handoff {rule_code}")
        return

    thread_id = conversation.get("external_thread_id", "?")
    push_name = conversation.get("push_name") or "Desconocido"

    history_lines = []
    for turn in recent_turns[-5:]:
        role = "👤 Cliente" if turn["role"] == "user" else "🤖 Bot"
        text = (turn.get("content_text") or "")[:120]
        history_lines.append(f"{role}: {text}")

    history = "\n".join(history_lines) or "(sin historial)"

    notification_text = (
        f"🔔 *Handoff {rule_code}* — atención requerida\n\n"
        f"👤 *Cliente:* {push_name}\n"
        f"📍 *Chat:* `{thread_id}`\n\n"
        f"💬 *Último mensaje:*\n{user_message[:300]}\n\n"
        f"📜 *Historial reciente:*\n{history}"
    )

    try:
        from telegram import Bot
        bot = Bot(token=bot_token)
        async with bot:
            await bot.send_message(
                chat_id=notify_target,
                text=notification_text,
                parse_mode="Markdown",
            )
        logger.info(f"Handoff notification sent for {rule_code} to {notify_target}")
    except Exception as exc:
        logger.error(f"Failed to send handoff notification: {exc}")
