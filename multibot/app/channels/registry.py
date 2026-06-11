from app.channels.base import ChannelAdapter
from app.channels.telegram import TelegramAdapter


def get_adapter(channel_type: str, channel_config: dict) -> ChannelAdapter:
    if channel_type == "telegram":
        return TelegramAdapter(
            bot_token=channel_config.get("bot_token", ""),
            secret_token=channel_config.get("secret_token", ""),
        )
    if channel_type == "whatsapp_official":
        from app.channels.whatsapp_official import WhatsAppOfficialAdapter
        return WhatsAppOfficialAdapter(
            phone_number_id=channel_config.get("phone_number_id", ""),
            access_token=channel_config.get("access_token", ""),
            app_secret=channel_config.get("app_secret", ""),
        )
    if channel_type == "whatsapp_unofficial":
        provider = channel_config.get("provider", "baileys")
        if provider == "evolution":
            from app.channels.evolution import EvolutionAPIAdapter
            return EvolutionAPIAdapter(
                base_url=channel_config.get("base_url", "http://localhost:8080"),
                api_key=channel_config.get("api_key", ""),
                instance=channel_config.get("instance", "multibot"),
            )
        # baileys (puente propio) y waha comparten interfaz REST simple
        from app.channels.whatsapp_unofficial import WhatsAppUnofficialAdapter
        return WhatsAppUnofficialAdapter(
            bridge_url=channel_config.get("base_url", channel_config.get("bridge_url", "http://localhost:3001")),
        )
    raise ValueError(f"Unknown channel type: {channel_type!r}")
