# Multibot — Plataforma de Atención Multi-Canal

Plataforma SaaS multi-tenant para bots de atención al cliente
soportando múltiples canales de mensajería y múltiples proveedores
de LLM (incluyendo modelos propios como MiniMax).

## Cliente piloto

**Green Glamping Chipaque + Parapente Volando con Tatán** (Colombia).
Bot comercial 24/7 con KB de 33 intents pre-hechos, ya en producción
sobre n8n/Telegram. Migración a Multibot como primer cliente.

## Características clave

- Multi-tenant (schema-separated)
- Multi-canal (WhatsApp oficial, WhatsApp no oficial, Telegram, Webchat)
- Multi-LLM (interface agnóstica, MiniMax primero, OpenAI-compat después)
- Multi-modal (texto, audio, imagen, video, documentos)
- Multi-herramienta (servidor y cliente MCP)
- Emulador / decisor visual (sandbox tipo PSeInt)
- Panel admin wizard lineal (no técnico friendly)
- TTS con voz clonada + cache + promoción automática
- Handoff inteligente con ventanas configurables (12/48/90d)
- Retroalimentación del cliente (workflow de aprobación)
- Dev en host → Docker para deploy

## Estructura

```
multibot/
├── app/                # Código Python (FastAPI)
│   ├── core/           # Tenant context, security, rate limit
│   ├── models/         # SQLAlchemy ORM
│   ├── schemas/        # Pydantic
│   ├── db/             # Sesión, base, migraciones
│   ├── channels/       # Adapters de canal (Wa of/no of, Tg, web)
│   ├── llm/            # Adapters de proveedor LLM
│   ├── bot/            # Cerebro: clasificador, memoria, handoff
│   ├── admin/          # Panel admin (FastAPI + Jinja + HTMX)
│   └── api/            # Webhooks entrantes
├── workers/            # ARQ workers (TTS, webhooks, notificaciones)
├── tests/              # pytest + pytest-asyncio
└── data/               # Archivos no-código (ver data/README.md)
```

## Stack

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy 2.0 async, Pydantic v2
- **Panel admin**: FastAPI + Jinja2 + HTMX + CSS custom (wizard lineal)
- **BD**: PostgreSQL 14+
- **Cache/cola**: Redis 7+
- **Async workers**: ARQ
- **WhatsApp oficial**: Meta Cloud API
- **WhatsApp no oficial**: microservicio Node.js + Baileys
- **Telegram**: python-telegram-bot
- **MCP**: servidor y cliente MCP
- **Container**: Docker + docker-compose

## Documentación

- `openspec/changes/multibot-platform/design.md` → diseño completo
- `openspec/changes/multibot-platform/tasks.md` → tareas (próximo)
- `data/README.md` → estructura de archivos

## Estado actual

Fase de diseño. No hay código todavía.

Para iniciar implementación, leer el design.md y seguir el roadmap
de sprints definido allí.
