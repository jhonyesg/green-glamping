# Intents

Definición declarativa de los intents que reconoce el bot y de las
reglas que disparan handoff a un humano.

## Archivos

| Archivo | Propósito |
|---|---|
| `intents.json` | Lista de intents: `name`, `keywords_regex`, `response_text`, `priority`, `requires_human`. Lo lee `app/bot/classifier.py`. |
| `handoff_triggers.json` | Reglas H01..Hn: a qué canal notificar (Telegram/email), con qué mensaje. |

Estos archivos son la **fuente de verdad** que el seed (`scripts/seed_green_glamping.py`)
carga en la tabla `kb_intents` del schema del tenant.
