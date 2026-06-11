"""First-contact welcome logic — sends cascade of messages to new users."""

from datetime import datetime, timezone


def get_welcome_text(variant: str = "default") -> str:
    hour = datetime.now(timezone.utc).hour  # UTC; adjust for Colombia (UTC-5)
    colombia_hour = (hour - 5) % 24

    if variant == "default":
        if 5 <= colombia_hour < 12:
            variant = "bienvenida_manana"
        elif 12 <= colombia_hour < 18:
            variant = "bienvenida_tarde"
        else:
            variant = "bienvenida_noche"

    VARIANTS = {
        "bienvenida_manana": "¡Buenos días! ☀️ Bienvenido/a a *Green Glamping Chipaque* y *Parapente Volando con Tatán* 🌿🪂\n\nEmpieza el día con una aventura. ¿En qué te podemos ayudar?",
        "bienvenida_tarde": "¡Buenas tardes! 🌤️ Bienvenido/a a *Green Glamping Chipaque* y *Parapente Volando con Tatán* 🌿🪂\n\n¿En qué te podemos ayudar?",
        "bienvenida_noche": "¡Buenas noches! 🌙 Bienvenido/a a *Green Glamping Chipaque* y *Parapente Volando con Tatán* 🌿🪂\n\nEscríbenos y con gusto te atendemos. ¿En qué te ayudamos?",
        "bienvenida_recurrente": "¡Hola de nuevo! 💚 Es un placer verte otra vez en *Green Glamping Chipaque*.\n\n¿En qué te podemos ayudar hoy?",
        "bienvenida_anuncio": "¡Hola! 👋 Bienvenido/a a *Green Glamping Chipaque* 🌿🪂\n\n✨ *¡Tenemos novedades!* Pregúntanos por nuestros nuevos combos y promociones.\n\n¿En qué te ayudamos?",
        "bienvenida_referido": "¡Hola! 👋 Alguien nos recomendó contigo 💚\n\nBienvenido/a a *Green Glamping Chipaque* y *Parapente Volando con Tatán* 🌿🪂\n\n¿En qué te podemos ayudar?",
    }

    return VARIANTS.get(variant, VARIANTS["bienvenida_tarde"])


async def send_first_contact(
    thread_id: str,
    adapter,
    welcome_variant: str = "default",
) -> None:
    """Send the 5-message welcome cascade for first-contact users."""
    from app.channels.base import OutboundMessage, ContentType

    text = get_welcome_text(welcome_variant)

    await adapter.send(OutboundMessage(
        thread_id=thread_id,
        text=text,
        content_type=ContentType.text,
    ))
    # Photos and closing message would be sent here with actual file_ids configured per tenant
