# Tasks: Multibot — Plataforma de Atención Multi-Canal

Este documento desglosa la implementación en tareas
verificables, agrupadas por sprint. El Sprint 0 es el esqueleto
base; el Sprint 1 hace funcionar Green Glamping end-to-end
sobre Telegram. Los sprints 2-5 están resumidos al final.

Cada tarea es un checkbox `- [ ]` que el sistema de apply puede
trackear.

---

## Precondiciones del entorno (verificar ANTES de Sprint 0)

Estas tareas no son código; son gates. Si alguna falla, hay
que resolverla antes de empezar a programar.

- [x] 0.1 Confirmar Python 3.11+ instalado (`python3 --version`)
- [x] 0.2 Elegir gestor de dependencias: `uv` (recomendado),
  `poetry`, o `pip + venv` clásico. Documentar la elección
  en `multibot/README.md`
- [x] 0.3 Confirmar acceso al container Postgres existente
  (host, puerto, usuario, password, nombre de BD). Crear
  `.env` raíz con `DATABASE_URL` apuntando a ese container
- [x] 0.4 Confirmar que el usuario Postgres tiene permisos
  para `CREATE SCHEMA` (necesario para multi-tenant)
- [x] 0.5 Confirmar Redis disponible localmente o
  instalarlo (`docker run -d -p 6379:6379 redis:7-alpine`)
  y obtener `REDIS_URL`
- [x] 0.6 Confirmar que existe el directorio `multibot/`
  con la estructura ya creada (sino, ejecutar el script
  de inicialización o seguir `multibot/README.md`)

---

## Sprint 0 — Skeleton (1-2 semanas)

### 1. Project setup

- [x] 1.1 Crear `pyproject.toml` unificado con:
  - Dependencias de runtime: `fastapi`, `uvicorn[standard]`,
    `sqlalchemy[asyncio]`, `alembic`, `asyncpg`, `psycopg2-binary`,
    `pydantic`, `pydantic-settings`, `redis`, `arq`,
    `structlog`, `loguru`, `python-decouple`, `cryptography`,
    `jinja2`, `python-multipart`
  - Dependencias de desarrollo: `pytest`, `pytest-asyncio`,
    `pytest-cov`, `ruff`, `mypy`, `pre-commit`, `httpx`
  - Configurar `[tool.ruff]`, `[tool.mypy]`, `[tool.pytest.ini_options]`
- [x] 1.2 Instalar dependencias con el gestor elegido
  (`uv sync` o `poetry install` o `pip install -e .[dev]`)
- [x] 1.3 Crear/verificar estructura de directorios según
  `multibot/README.md` y poblar `app/__init__.py` con
  versión `0.1.0` y metadata del paquete
- [x] 1.4 Crear `.env.example` raíz con todas las variables
  esperadas (DATABASE_URL, REDIS_URL, SECRET_KEY,
  LOG_LEVEL, ENVIRONMENT) y crear `.env` local con valores
  reales (NO commitear)
- [x] 1.5 Crear `app/config.py` con `Settings` (Pydantic v2
  y pydantic-settings) leyendo de `.env` con validación
  de tipos y un método `get_database_url()` que retorna el
  URL con el driver asyncpg
- [x] 1.6 Crear `app/core/logging.py` configurando
  `loguru` + `structlog` juntos: formato JSON en producción
  (`ENVIRONMENT=production`), formato legible con colores
  en dev, request_id por request, integración con FastAPI
  middleware
- [x] 1.7 Crear `Dockerfile` (multi-stage, python:3.11-slim)
  y `docker-compose.yml` base con servicios `web`, `worker`,
  `redis` (Postgres queda en el container existente del
  usuario, no se incluye en compose)
- [x] 1.8 Crear `tests/conftest.py` con fixtures base:
  `event_loop`, `async_client`, `db_session` (con cleanup),
  `redis_client`, `tenant_factory`
- [x] 1.9 Crear `.gitignore` raíz excluyendo: `__pycache__/`,
  `*.pyc`, `.env`, `.venv/`, `venv/`, `dist/`, `*.egg-info/`,
  `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`,
  `data/media/received/`, `data/media/sent/tts/`,
  `data/media/sent/temp/`, `data/exports/db_dumps/`,
  `data/media/quarantine/`, `data/uploads/tenants/*/runtime/`
- [x] 1.10 Crear `Makefile` con targets útiles: `install`,
  `dev` (uvicorn --reload), `test`, `lint`, `format`,
  `migrate`, `worker`, `docker-up`, `docker-down`

### 2. Database foundation

- [x] 2.1 Crear `app/db/session.py` con engine async
  (`create_async_engine`), session factory
  (`async_sessionmaker`), `get_session()` dependency
  para FastAPI, y `get_schema_session(schema_name)` para
  tenants
- [x] 2.2 Configurar Alembic en `app/db/migrations/`
  apuntando al schema `public` para migraciones globales
  (planes, planes_features, etc.)
- [x] 2.3 Crear `app/db/base.py` con `Base` (declarative
  base) y `BaseSchema` (base con `__table_args__` que
  permite configurar schema dinámicamente)
- [x] 2.4 Crear modelo `Plan` en `app/models/plan.py`
  (id, name, max_concurrent_chats, channels_included
  jsonb, monthly_price, llm_tokens_included, is_active)
  con migración Alembic en `public`
- [x] 2.5 Crear modelo `Tenant` en `app/models/tenant.py`
  con `operation_mode` (enum SQLAlchemy
  autonomous/assisted/hybrid), `slug` único, `status`
  (provisioning/active/suspended/archived), `plan_id`
  FK, `retention_days`, `payment_message_template` jsonb,
  `welcome_variant` str; métodos `set_schema_search_path()`
  y `is_active()`
- [x] 2.6 Crear modelo `Channel` en
  `app/models/channel.py` (tenant_id FK, type enum
  whatsapp_official/whatsapp_unofficial/telegram/webchat,
  credentials jsonb, is_active, webhook_url, last_seen_at)
- [x] 2.7 Crear modelo `LLMProvider` en
  `app/models/llm_provider.py` (tenant_id FK, provider_name,
  model, api_key cifrado, base_url, capabilities jsonb,
  stt_fallback jsonb, is_active, priority)
- [x] 2.8 Implementar `app/core/tenant.py` con:
  - `current_tenant: ContextVar[Tenant | None]`
  - `bind_tenant(tenant)` context manager
  - `get_current_tenant()` getter
  - `get_tenant_from_path(slug)` que consulta la BD
  - `get_tenant_from_request(request)` dependency de FastAPI
- [x] 2.9 Implementar `app/core/security.py` con:
  - `FernetKeyManager` que carga la key de `SECRET_KEY`
  - `encrypt_credentials(plain: dict) -> str`
  - `decrypt_credentials(encrypted: str) -> dict`
  - Tests unitarios con datos de ejemplo
- [x] 2.10 Crear script `scripts/create_tenant.py` con
  CLI (`python -m scripts.create_tenant --slug demo
  --plan-id 1`) que: crea el schema `tenant_<slug>`,
  corre migraciones de tenant (tablas globales al schema),
  crea el row en `public.tenants`, devuelve el ID
- [x] 2.11 Crear `data/seeds/demo_tenant.json` con
  config mínima (nombre "Demo Tenant", slug "demo",
  operation_mode "hybrid", plan_id 1, canales mock
  inactivos)
- [x] 2.12 Crear migración Alembic inicial (rev1) en
  `public/` con planes y tenants
- [x] 2.13 Crear template de migración Alembic
  `app/db/migrations/versions/tenant_template.py` que
  las migraciones por tenant extiendan (tablas:
  channels, llm_providers, kb_intents, conversations,
  messages, etc.)
- [x] 2.14 Probar: correr `alembic upgrade head` y
  luego `python -m scripts.create_tenant --slug demo`
  y verificar que existe `tenant_demo` en la BD

### 3. Skeleton web app

- [x] 3.1 Crear `app/main.py` con FastAPI app:
  - `lifespan` context manager (init pools, close on
    shutdown, carga config)
  - Middleware de logging con request_id
  - Exception handlers para ValidationError, SQLAlchemyError,
    Exception genérica
  - Incluir routers: `app.api.webhooks`, `app.admin.routes.dashboard`
- [x] 3.2 Crear `app/api/webhooks.py` con router
  placeholder (solo define las rutas vacías, los adapters
  se llenan en Sprint 1)
- [x] 3.3 Crear endpoint `GET /health` que retorna
  `{"status": "ok", "db": "ok", "redis": "ok",
  "version": "0.1.0"}` y verifica conectividad real
  ejecutando `SELECT 1` y `PING` redis
- [x] 3.4 Crear endpoint raíz `GET /` que retorna
  `{"name": "Multibot", "version": "0.1.0",
  "docs": "/admin"}`
- [x] 3.5 Configurar CORS en `app/main.py` con origins
  permitidos desde variable `CORS_ORIGINS` (CSV)
- [x] 3.6 Crear `app/admin/templates/base.html` (Jinja2)
  con: navbar, footer, HTMX 1.9 desde CDN, CSS link
  al static, bloque `{% block content %}{% endblock %}`
- [x] 3.7 Crear `app/admin/templates/dashboard.html`
  que extiende base y muestra "Bienvenido a Multibot"
  con la versión y un enlace a `/health`
- [x] 3.8 Crear `app/admin/routes/dashboard.py` con
  router que monta el dashboard, con template Jinja2
  configurado
- [x] 3.9 Crear `app/admin/static/style.css` base con
  variables CSS (colores verde/azul, fuentes, espaciado),
  reset básico, y estilos para navbar, cards, botones
- [x] 3.10 GATE: Levantar la app con
  `uvicorn app.main:app --reload` y verificar:
  - `GET /` retorna 200 con JSON esperado
  - `GET /health` retorna 200 con `db: ok, redis: ok`
  - `GET /admin` retorna 200 con HTML del dashboard
  - Logs visibles con request_id
- [x] 3.11 GATE: Conectar al Postgres existente y
  crear el primer tenant de prueba corriendo
  `python -m scripts.create_tenant --slug demo`,
  verificando que el schema `tenant_demo` existe y
  tiene las tablas base

---

## Sprint 1 — Green Glamping funcional (2-3 semanas)

> **Dependencias**: requiere Sprint 0 completo (tasks
> 0.1-0.6, 1.1-1.10, 2.1-2.14, 3.1-3.11 todas verificadas).

### 4. KB seed and classifier

- [x] 4.1 Crear modelo `KBIntent` en
  `app/models/kb_intent.py` (tenant_id FK, intent_name,
  keywords_regex, response_text, response_audio_id
  nullable FK, response_image_ids jsonb, handoff_rule,
  requires_human default false, human_reason text
  nullable, priority, status enum active/draft/
  pending_approval, source enum seed/manual/
  client_feedback)
- [x] 4.2 Crear tabla `handoff_rules` (id, tenant_id,
  mode enum, rule_code, trigger_intent, is_active,
  priority, notify_channel, notify_target,
  custom_message) en el schema del tenant
- [x] 4.3 Generar migración Alembic de tenant
  (aplicada al crear nuevo tenant) con las tablas:
  channels, llm_providers, kb_intents, handoff_rules,
  conversations, messages, message_attachments,
  feedback_tickets, handoff_events, reservations,
  availability_sources, availability_slots,
  media_assets, audit_log
- [x] 4.4 Crear `data/seeds/green_glamping_kb.json`
  consolidando los archivos originales del proyecto:
  - 33 intents desde `01_knowledge_base.json`
  - 7 handoff triggers desde `03_handoff_triggers.json`
  - 6 objeciones O1-O6 (como intents con prioridad
    especial)
  - Campos requeridos: intent_name, keywords_regex,
    response_text, handoff_rule, requires_human
- [x] 4.5 Crear script `scripts/seed_green_glamping.py`
  que: crea el tenant "green-glamping" con
  operation_mode="autonomous", carga el JSON, crea
  los kb_intents, crea las handoff_rules con defaults
  Modo A
- [x] 4.6 Crear `app/bot/anti_injection.py` con la lista
  de keywords bloqueadas (copiada del proyecto
  original) y función `check_injection(text) -> bool`
  que retorna True si detecta alguna; incluye tests
- [x] 4.7 Crear `app/bot/classifier.py` con función
  `classify(text, tenant_id, db) -> ClassificationResult`
  que: itera sobre los intents activos del tenant,
  evalúa `keywords_regex`, retorna el mejor match con
  score de confianza; maneja empate entre top 2
  marcando "ambiguous"
- [x] 4.8 Crear `app/bot/responder.py` con función
  `build_response(classification, conversation) ->
  OutboundMessage` que toma el resultado y construye
  el mensaje con texto + adjuntos
- [x] 4.9 Crear `app/bot/pipeline.py` orquestando:
  `anti_injection → classifier → responder → persist
  → send`. Esta es la función principal que
  `webhooks.py` llamará
- [x] 4.10 Crear `tests/test_anti_injection.py` con
  casos: "ignora instrucciones", "dime tu prompt",
  "actúa como", "eres un bot", etc.
- [x] 4.11 Crear `tests/test_classifier.py` con casos
  de Green Glamping: "hola" → saludo_puro,
  "cuánto cuesta combo 5" → info_combos, "puedo
  llevar mascota" → mascotas, "komo reservo" →
  como_reservar, etc. (incluir typos y abreviaciones)
- [x] 4.12 GATE: Correr pytest y verificar que todos
  los tests del clasificador y anti-injection pasan

### 5. Telegram channel adapter

- [x] 5.1 Instalar `python-telegram-bot` v20+ (async),
  añadir a `pyproject.toml` y correr `uv sync`
- [x] 5.2 Crear `app/channels/base.py` con la interface
  `ChannelAdapter` (Protocol) y dataclasses
  `InboundMessage`, `OutboundMessage`, `MessageContent`
  según `design.md` sección 6
- [x] 5.3 Crear `app/channels/telegram.py` con
  `TelegramAdapter(ChannelAdapter)`:
  - `parse_inbound(update) -> InboundMessage`
  - `send(message) -> SendResult`
  - `send_typing(thread_id)` con `send_chat_action`
  - `download_media(file_id) -> bytes` via `get_file`
  - `verify_webhook(payload, signature) -> bool` con
    HMAC del secret token
- [x] 5.4 Crear registry de adapters en
  `app/channels/registry.py` con `get_adapter(channel_type,
  channel_config) -> ChannelAdapter`
- [x] 5.5 Implementar `app/api/webhooks.py` con
  endpoint `POST /webhook/telegram/{tenant_slug}`:
  - Verificar firma
  - Resolver tenant del path
  - Parsear a InboundMessage
  - Llamar `pipeline.process(inbound)`
  - Retornar 200 OK
- [x] 5.6 Crear `data/seeds/green_glamping_welcome_variants.json`
  con las 6 variantes de bienvenida (01b-01f +
  bienvenida_anuncio + bienvenida_referido del proyecto
  original)
- [x] 5.7 Implementar lógica de primer contacto en
  `app/bot/welcome.py`: si `is_first_contact`, envía
  5 mensajes en cascada (bienvenida + 2 fotos
  portafolio + saludo por hora + cierre)
- [ ] 5.8 GATE: Probar end-to-end con el bot real de
  Telegram:
  - Enviar "Hola" → respuesta de saludo
  - Enviar "Cuánto cuesta combo 5" → info del combo
  - Verificar en logs: `matched_via: regex`,
    `llm_calls: 0`, `latency_ms < 2000`
- [ ] 5.9 Configurar webhook de Telegram apuntando a
  `https://<host>/webhook/telegram/green-glamping`
  usando `setWebhook` con el secret token
- [x] 5.10 Documentar el cutover en `docs/cutover.md`:
  pasos exactos para pasar del bot de n8n al nuevo
  bot, manteniendo el original funcionando

### 6. Conversation memory and basic handoff

- [x] 6.1 Crear modelo `Conversation` en
  `app/models/conversation.py` (tenant_id, channel_id,
  external_thread_id, user_external_id, push_name,
  operation_mode_snapshot, state enum
  active/in_handoff/ready_for_payment/awaiting_proof/
  confirmed/closed/cancelled_*, in_handoff bool,
  handoff_at, handoff_rule, handoff_expires_at,
  last_message_at, last_responder enum bot/human)
- [x] 6.2 Crear modelo `Message` en
  `app/models/message.py` (conversation_id FK, role
  enum user/bot/human, content_type enum text/audio/
  image/video/document/mixed, content_text, intent_id
  FK nullable, matched_via enum regex/llm/exact/
  fallback, llm_tokens_used int, latency_ms int,
  feedback enum none/good/bad, feedback_note text,
  ts) con índice `(conversation_id, ts)`
- [x] 6.3 Crear `app/bot/memory.py` con:
  - `get_or_create_conversation(tenant, channel,
    external_thread_id, user) -> Conversation`
  - `get_recent_turns(conversation_id, k=10) ->
    list[Message]`
  - `persist_message(conversation, role, content,
    metadata) -> Message`
- [x] 6.4 Modificar `app/bot/pipeline.py` para:
  - Antes de clasificar: cargar/crear conversación
  - Después de clasificar: persistir mensaje del
    usuario con intent detectado
  - Después de responder: persistir mensaje del bot
    con `latency_ms` medido
- [x] 6.5 Crear `app/bot/handoff.py` con:
  - `trigger_handoff(conversation, rule, reason)`
    que actualiza estado, calcula
    `handoff_expires_at`, crea `handoff_event`, y
    envía push de notificación
  - `is_in_handoff_pause(conversation) -> bool`
    que evalúa las ventanas configuradas
  - `resume_conversation(conversation)` que resetea
    el estado
- [x] 6.6 Implementar lógica de "callar inteligente"
  al inicio del pipeline: si conversación está en
  handoff y dentro de ventana corta, loguear el
  mensaje pero no responder (y reenviar al humano
  si la ventana larga ya pasó)
- [x] 6.7 Crear seed de `handoff_rules` para Green
  Glamping con los defaults de Modo A
  (H01: cliente confirma listo para pagar, etc.)
- [x] 6.8 Implementar notificación al humano en
  `app/notifications/human_notify.py` que envía por
  Telegram (configurado por tenant) con el contexto
  completo y deep link al panel
- [ ] 6.9 Configurar el contacto humano de Green
  Glamping (Johana) y su canal de notificación
  (Telegram chat_id) en el seed o en `.env`
- [x] 6.10 Crear `tests/test_handoff.py` con escenarios:
  handoff temprano, ventana de pausa, retoma después
  de 48h, notificación al humano
- [ ] 6.11 GATE: Probar handoff end-to-end:
  - Enviar mensaje con todos los datos (nombre,
    cédula, fecha, combo)
  - Verificar que el bot hace handoff
  - Verificar que el bot no responde más durante
    la ventana de pausa
  - Verificar que Johana recibe la notificación

### 7. Sprint 1 verification

- [ ] 7.1 El bot de Telegram responde correctamente a
  las 33 preguntas de la KB sin errores
- [ ] 7.2 El bot detecta intents compuestos
  (saludo + pregunta en un solo mensaje) y prioriza
  la pregunta
- [ ] 7.3 El bot tolera typos y abreviaciones comunes
  (komo, kuesta, glampin, combos, preio, penti)
- [ ] 7.4 El bot hace handoff H01 al recibir datos
  completos y notifica a Johana por Telegram
- [ ] 7.5 El bot calla durante la ventana de handoff
  configurada (12h)
- [ ] 7.6 Los mensajes se persisten en `messages` y la
  memoria de 10 turnos funciona (verificar con
  pregunta que requiere contexto)
- [ ] 7.7 Latencia < 2s para respuestas regex (medido
  con `messages.latency_ms`, promedio < 2000)
- [ ] 7.8 Cero invocaciones al LLM en el flujo normal
  (verificar con `SELECT COUNT(*) FROM messages WHERE
  llm_tokens_used > 0` → debe ser 0 o muy bajo)
- [ ] 7.9 El bot de n8n original puede seguir
  funcionando en paralelo (no se rompe nada durante
  la fase de prueba)
- [ ] 7.10 Cutover ejecutado: webhook de Telegram
  apunta al nuevo bot, n8n queda como backup
  (siguiendo `docs/cutover.md`)

---

## Sprint 2 — Panel admin visual (resumen)

### 8. Wizard de 6 pasos

- [x] 8.1 Crear `app/admin/routes/wizard.py` con las 6
  rutas: paso 1 (datos), paso 2 (modo), paso 3 (canal),
  paso 4 (calendario), paso 5 (assets), paso 6 (KB + test)
- [x] 8.2 Implementar navegación con HTMX: cada paso
  tiene formulario que envía POST y avanza
- [x] 8.3 Implementar vista previa del flujo según modo
  elegido en paso 2 (diagrama ASCII o HTML del flujo)
- [x] 8.4 Crear `scripts/onboard_tenant.py` que
  automatiza la creación completa vía API interna
  (útil para crear el segundo tenant sin wizard)
- [ ] 8.5 GATE: Probar wizard completo creando un
  segundo tenant "test_tenant" de inicio a fin

### 9. KB editor y conversaciones

- [x] 9.1 Pantalla de KB con lista de intents, búsqueda
  por nombre y filtros por status / requires_human
- [x] 9.2 Editor de intent (form con todos los campos)
  con toggle `requires_human` y campo de razón
- [x] 9.3 Pantalla de conversaciones con lista paginada
  y filtros por estado (active, in_handoff, etc.)
- [x] 9.4 Detalle de conversación con timeline de
  mensajes y quick actions (mark good/bad, edit
  intent, view reservation)
- [x] 9.5 Botones "marcar buena/mala" y "editar intent"
  con creación automática de feedback tickets

### 10. Dashboard de métricas

- [x] 10.1 Vista de métricas agregadas: volumen,
  latencia, top intents, conversion rate por modo
- [x] 10.2 Gráficos simples (Chart.js via CDN) para
  visualizar tendencias 7/30/90 días
- [x] 10.3 Vista de feedback tickets pendientes con
  aprobar/rechazar y razón

---

## Sprint 3 — Multi-canal + LLM agnóstico (resumen)

### 11. WhatsApp oficial

- [x] 11.1 Implementar `WhatsAppOfficialAdapter` con
  Meta Cloud API SDK
- [x] 11.2 Manejo de templates pre-aprobados para
  mensajes fuera de ventana 24h
- [x] 11.3 Endpoint `/webhook/whatsapp_official/{slug}`
  con verificación de `X-Hub-Signature-256`
- [ ] 11.4 Flujo completo probado con número real

### 12. WhatsApp no oficial

- [x] 12.1 Crear microservicio Node.js separado
  `whatsapp-nooficial/` con Baileys (carpeta nueva
  fuera de multibot/, en la raíz del proyecto)
- [x] 12.2 Endpoint REST en el microservicio:
  `/send`, `/messages`, `/status`, `/qr`
- [x] 12.3 Reconexión automática de sesión con QR de
  respaldo y alerta al admin si se desconecta
- [x] 12.4 Implementar `WhatsAppUnofficialAdapter` en
  Python que habla con el microservicio

### 13. LLM provider abstraction

- [x] 13.1 Crear `app/llm/base.py` con `LLMProvider`
  interface (Protocol)
- [x] 13.2 Implementar `MiniMaxAdapter` (cliente HTTP
  al endpoint MiniMax del usuario, configurable)
- [x] 13.3 Implementar `OpenAICompatAdapter` con
  configuración flexible de base_url y modelos
- [x] 13.4 Crear `LLMRouter` que selecciona el provider
  del tenant y maneja failover
- [x] 13.5 Implementar STT routing inteligente según
  `capabilities.audio_input` (multimodal vs Whisper)
- [ ] 13.6 GATE: Probar que el LLM solo se invoca
  en casos no cubiertos por regex y medir latencia

### 14. Emulador

- [x] 14.1 Endpoint `POST /admin/simulate` con
  parámetros tenant, thread, message
- [x] 14.2 Retornar decision tree trace con todos los
  pasos y métricas (latencia, llm_calls, cost)
- [x] 14.3 Visualización en el panel como flowchart
  (HTML/CSS o librería ligera)
- [x] 14.4 Botón "Export as test" que genera pytest
  file descargable

---

## Sprint 4 — TTS + retroalimentación + MCP (resumen)

### 15. TTS system

- [x] 15.1 Configuración de voz clonada por tenant en
  el panel (subir muestra o configurar endpoint)
- [x] 15.2 Implementar TTS generation vía provider
  configurado (MiniMax TTS o servicio dedicado)
- [x] 15.3 Implementar cache de TTS con `tts_cache` y
  hash de texto (sha256)
- [x] 15.4 Implementar promoción automática a
  pregenerated cuando `use_count > threshold`
- [x] 15.5 Rotación de variantes de voz (warm_1,
  warm_2, etc.) configurable por tenant

### 16. Feedback workflow

- [x] 16.1 UI para que el cliente del tenant envie
  feedback (4 tipos: bad_response, new_intent,
  edit_response, free_text)
- [x] 16.2 Cola de tickets pendientes en el panel admin
  con badges de prioridad
- [x] 16.3 Aprobar/rechazar con notificaciones
  (al cliente que envió el feedback)
- [x] 16.4 Métricas de feedback (tiempo de resolución,
  ratio aprobar/rechazar, top intents con "bad")

### 17. MCP server

- [x] 17.1 Implementar servidor MCP en `/mcp` con las 6
  tools expuestas
- [x] 17.2 Implementar los 3 resources con scoping por
  tenant
- [x] 17.3 Cliente MCP stub para desarrollo con un
  servidor mock local
- [x] 17.4 Autenticación por tenant API key

### 18. Reservation lifecycle (in progress desde Sprint 1)

- [x] 18.1 Modelo `Reservation` y tabla
- [x] 18.2 `AvailabilityProvider` interface + adapter
  tabla local (los demás adapters en Sprint 4)
- [x] 18.3 Validación de disponibilidad en pipeline
  (Modo A/C)
- [x] 18.4 Plantilla de mensaje de pago por tenant
- [x] 18.5 Detección de comprobante vía vision
- [x] 18.6 Confirmación de pago por humano en panel
- [x] 18.7 Recordatorios 24h/48h
- [x] 18.8 Estados de reserva en panel

---

## Sprint 5 — Pulido (resumen)

### 19. Multimodal pipeline

- [x] 19.1 Vision para imágenes (delegar al provider
  multimodal o fallback)
- [x] 19.2 STT para audio (routing inteligente)
- [x] 19.3 Extracción de audio + frame de video
- [x] 19.4 Manejo de documentos PDF

### 20. Media retention

- [x] 20.1 Job nocturno ARQ scheduler que aplica la
  política de retención
- [x] 20.2 Movimiento a quarantine antes de hard delete
- [x] 20.3 Métricas de espacio liberado por día
- [x] 20.4 UI de "próxima limpieza: en Xh"

### 21. Documentación y handover

- [x] 21.1 README completo de deploy con docker-compose
- [x] 21.2 Guía de onboarding para nuevos tenants
- [x] 21.3 Guía de troubleshooting común
- [x] 21.4 Runbook de operación diaria
- [x] 21.5 Script de migración de Green Glamping desde
  n8n a Multibot paso a paso (cutover definitivo)

---

## Notas de ejecución

### Orden crítico por fase

- **Precondiciones (0.x)**: resolver ANTES de cualquier
  task de código. Si Python no está, no se puede empezar.
- **Sprint 0**: tasks 1.x → 2.x → 3.x son **secuenciales**
  (setup antes de modelos antes de app). GATES 3.10 y 3.11
  validan que todo el Sprint 0 funciona antes de seguir.
- **Sprint 1**: tasks 4.x → 5.x → 6.x son
  **secuenciales con dependencias cruzadas** (ver nota
  arriba de cada sección).
- **Sprint 2-5**: pueden tener paralelismo entre grupos
  (ej. trabajar en TTS y feedback en paralelo).

### GATES del Sprint 0

Los puntos críticos de validación son:

- **Gate 1.2**: dependencias instaladas (verificar con
  `python -c "import fastapi, sqlalchemy"`)
- **Gate 3.10**: app levanta y endpoints responden
- **Gate 3.11**: conexión a Postgres funciona y primer
  tenant se crea

Si cualquiera falla, NO continuar al Sprint 1.

### Estimación

- Sprint 0: 1-2 semanas (1 dev fullstack)
- Sprint 1: 2-3 semanas (validación go/no-go)
- Sprint 2-5: 6-8 semanas adicionales

### Verificación

Cada tarea `[ ]` es verificable manualmente o con un
test. Marcar como `[x]` solo cuando se verifica
explícitamente. El sistema de apply reportará el
progreso automáticamente.
