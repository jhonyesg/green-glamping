# Multibot — Diseño de la plataforma

**Estado**: Borrador inicial (fase de descubrimiento cerrada)
**Fecha**: 2026-06-09
**Cliente piloto**: Green Glamping Chipaque + Parapente Volando con Tatán

---

## 1. Visión y alcance

**Multibot** es una plataforma SaaS multi-tenant para crear y operar
bots de atención al cliente sobre múltiples canales de mensajería,
con LLM configurable por tenant (incluyendo modelos propios como
MiniMax, 12B parámetros, multimodal).

### Camino de construcción

**Camino B**: implementar Green Glamping como primer cliente sobre
cimiento multi-tenant desde el día 1. Cuando llegue el cliente #2,
será "agregar una fila a la BD", no reescribir nada.

### Lo que es

- Plataforma multi-tenant multi-canal
- Soporta 200-300 chats/día de entrada publicitaria con picos
  moderados (no 300 concurrentes sostenidos)
- LLM agnóstico (cualquier provider OpenAI-compatible, MiniMax
  primero)
- Panel admin visual con flujo wizard lineal
- Emulador / decisor tipo PSeInt para simular sin producción
- TTS con voz clonada + cache + promoción automática
- Handoff inteligente con ventanas configurables
- Retroalimentación del cliente con workflow de aprobación
- Servidor y cliente MCP para interoperabilidad
- Multimodal nativo: texto, audio (STT), imagen (vision), video
  (extracción de audio + frame)

### Modos de operación por tenant

Cada tenant opera en uno de tres modos (configurable y
cambiable en caliente desde el panel):

- **Modo A — Bot gestiona todo (autónomo)**: el bot valida
  disponibilidad (calendario propio o Google Calendar),
  confirma pre-reserva, hace handoff SOLO para validación
  de pago. El humano solo valida el comprobante.
- **Modo B — Humano gestiona (asistido)**: el bot NO valida
  disponibilidad ni confirma nada. Apenas hay interés real
  (datos clave entregados), se hace handoff. El humano hace
  disponibilidad, confirmación, envío de datos de pago y
  cierre. El bot filtra y prepara el contexto.
- **Modo C — Híbrido (recomendado por defecto)**: el bot
  hace lo que puede (Modo A por defecto) pero ciertos
  intents o servicios están marcados como "requiere
  humano" (eventos corporativos, paquetes personalizados).
  El bot escala automáticamente cuando no puede resolver.

El modo afecta:
- Trigger de handoff (cuándo se hace)
- Si el bot consulta calendario
- Quién envía los datos de pago (bot vs humano)
- El árbol de decisión del clasificador

### Lo que NO es (no-goals)

- No es un constructor de bots sin código estilo manychat
- No es un contact center omnicanal con ACD/PBX
- No es una plataforma de marketing automation
- No es analytics avanzado / BI (solo métricas operativas)
- No es multi-idioma sofisticado (i18n básico sí, pero no es el foco)
- No es self-service para el cliente final (panel admin es para
  nosotros, el cliente aporta retroalimentación, no configura)

---

## 2. Nombre y contexto

- **Nombre interno**: `multibot`
- **Nombre comercial**: "Plataforma de Atención"
- **Tipo de producto**: SaaS B2B incipiente
- **Cliente actual**: Green Glamping Chipaque (turismo, Colombia)
- **Canal actual del cliente**: Telegram (bot en n8n)
- **Canales objetivo**: WhatsApp oficial + no oficial, Telegram,
  Webchat, voz (V2)

---

## 3. Stack tecnológico

| Capa              | Tecnología                          | Razón                          |
|-------------------|-------------------------------------|--------------------------------|
| Backend           | Python 3.11+ / FastAPI              | Async, ecosistema IA           |
| ORM               | SQLAlchemy 2.0 (async)              | Maduro, async-friendly         |
| Migraciones       | Alembic                             | Estándar con SQLAlchemy        |
| Validación        | Pydantic v2                         | Tipado fuerte, schemas         |
| BD principal      | PostgreSQL 14+                      | Multi-tenant, JSONB, full-text |
| Cache / cola      | Redis 7+                            | Memoria corta, rate limit      |
| Workers async     | ARQ                                 | Async, simple, suficiente      |
| Panel admin       | FastAPI + Jinja2 + HTMX + CSS       | Wizard lineal, 1 solo stack    |
| Templates         | Jinja2                              | Familiar, no SPA               |
| Webhook server    | FastAPI nativo                      | Ya incluido                    |
| Wa oficial        | Meta Cloud API SDK                  | Estándar industria             |
| Wa no oficial     | Microservicio Node.js + Baileys     | Lo más confiable no-oficial    |
| Telegram          | python-telegram-bot                 | Maduro, async support          |
| MCP               | Servidor y cliente MCP              | Interoperabilidad IA           |
| Logging           | Loguru + structlog                  | Simple, estructurado           |
| Tests             | pytest + pytest-asyncio             | Estándar                       |
| Container         | Docker + docker-compose             | Dev → prod                     |
| Deploy            | VPS único (Hetzner/DO)              | Suficiente para MVP            |
| Secrets           | .env + python-decouple              | Simple, suficiente MVP         |
| Scheduler         | ARQ cron + APScheduler              | Limpieza nocturna              |

---

## 4. Arquitectura de alto nivel

```
                         ┌─────────────────────────────┐
                         │   PANEL ADMIN (wizard)      │
                         │   FastAPI + Jinja + HTMX    │
                         └──────────────┬──────────────┘
                                        │ gestiona
                                        ▼
   ┌─────────────┐    ┌──────────────────────────────────────┐
   │   CANALES   │───▶│          NÚCLEO MULTIBOT             │
   │  (adapters) │◀───│                                      │
   │             │    │  ┌──────────┐  ┌──────────────┐     │
   │ • Wa of     │    │  │Clasif.   │  │   Router     │     │
   │ • Wa no of  │    │  │híbrido   │──│   LLM        │     │
   │ • Telegram  │    │  │regex→LLM │  │ (por tenant) │     │
   │ • Webchat   │    │  └────┬─────┘  └──────┬───────┘     │
   │             │    │       │                │             │
   └─────────────┘    │       ▼                ▼             │
        ▲             │  ┌──────────┐  ┌──────────────┐     │
        │             │  │  KB por  │  │  TTS Cache   │     │
        │             │  │  tenant  │  │  (voz clon.) │     │
        │             │  └──────────┘  └──────────────┘     │
        │             │       │                │             │
        │             │       ▼                ▼             │
        │             │  ┌──────────────────────────┐       │
        │             │  │  Generador respuesta     │       │
        │             │  │  (texto/audio/imagen)    │       │
        │             │  └────────────┬─────────────┘       │
        │             └───────────────┼─────────────────────┘
        │                             │
        │                             ▼
        │                     ┌──────────────┐
        └─────────────────────│  HANDOFF     │
             (pausa 12-48h)   │  inteligente │
                              └──────┬───────┘
                                     │ notifica
                                     ▼
                              ┌──────────────┐
                              │  HUMANO      │
                              │  (Johana)    │
                              └──────────────┘

   CAPAS TRANSVERSALES:
   ┌────────────┐  ┌────────────┐  ┌─────────────┐  ┌──────────┐
   │  EMULADOR  │  │  MCP       │  │  RETRO-     │  │  LOGS +  │
   │  /DECISOR  │  │  server +  │  │  ALIMENTA-  │  │  MÉTRI-  │
   │  (sandbox) │  │  client    │  │  CIÓN       │  │  CAS     │
   └────────────┘  └────────────┘  └─────────────┘  └──────────┘
```

### Servicios

| Servicio                     | Puerto | Responsabilidad                       |
|------------------------------|--------|---------------------------------------|
| `multibot-web`               | 8000   | API + panel admin + webhooks          |
| `multibot-worker`            | -      | ARQ workers (TTS, handoff, limpieza)  |
| `multibot-wha-nooficial`     | 3001   | Microservicio Node + Baileys          |
| `postgres`                   | 5432   | BD principal                          |
| `redis`                      | 6379   | Cache + cola + memoria corta          |

### Protocolos entre servicios

- Web ↔ Worker: ARQ queue (Redis)
- Web ↔ Wa no oficial: HTTP REST
- Web ↔ Postgres: asyncpg (SQLAlchemy async)
- Web ↔ Redis: redis-py async
- Externos (Wa of, Tg, MCP): HTTPS webhook entrante

---

## 5. Modelo de datos (multi-tenant)

### Aislamiento: schema-separated

Cada tenant tiene su propio schema en una sola instancia Postgres.
El `public` schema contiene tablas globales (admin, planes, etc).

### Diagrama ER (simplificado)

```
  tenants
  ├── id, name, slug, status, plan_id, created_at
  ├── operation_mode (enum: 'autonomous' | 'assisted' | 'hybrid')
  ├── llm_config_id (FK)
  ├── storage_quota_gb
  ├── retention_days (default 90)
  ├── welcome_variant_id (FK)
  ├── handoff_human_contact, handoff_pause_short_h,
  │   handoff_pause_long_h, handoff_resume_h
  ├── payment_message_template (jsonb, ver sección 17)
  │
  ├── plans
  │     id, name, max_concurrent_chats, channels_included,
  │     monthly_price, llm_tokens_included
  │
  ├── llm_providers (multi-tenant, multi-key)
  │     id, tenant_id, provider_name, model,
  │     api_key (encrypted), base_url,
  │     capabilities (jsonb: text, audio_in, audio_out,
  │                   image_in, video_in),
  │     stt_fallback (jsonb: provider, model, endpoint),
  │     is_active, priority (para failover)
  │
  ├── channels
  │     id, tenant_id, type (whatsapp_official/
  │     whatsapp_unofficial/telegram/webchat),
  │     credentials (jsonb, encrypted),
  │     is_active, webhook_url, last_seen_at
  │
  ├── kb_intents
  │     id, tenant_id, intent_name, keywords_regex,
  │     response_text, response_audio_id (FK → media_assets),
  │     response_image_ids (jsonb array),
  │     handoff_rule (H01..H07), priority,
  │     requires_human (bool, default false),
  │     human_reason (text, nullable),
  │     status (active/draft/pending_approval),
  │     source (seed/manual/client_feedback)
  │
  ├── media_assets
  │     id, tenant_id, category (portfolio/pregenerated/
  │     kb_asset/tts/temp/received), file_name, storage_path,
  │     mime_type, size_bytes, duration_seconds,
  │     external_url, channel_specific_id,
  │     voice_variant, use_count, is_promoted,
  │     transcript, vision_description, thumbnail_path,
  │     is_active, created_at, expires_at
  │
  ├── conversations
  │     id, tenant_id, channel_id, external_thread_id,
  │     user_external_id, push_name,
  │     operation_mode_snapshot (modo activo al crear),
  │     state (active/in_handoff/ready_for_payment/
  │            awaiting_proof/confirmed/closed/
  │            cancelled_by_user/cancelled_auto/
  │            cancelled_by_human),
  │     in_handoff, handoff_at, handoff_rule,
  │     handoff_expires_at, last_message_at,
  │     last_responder (bot/human)
  │
  ├── messages
  │     id, conversation_id, role (user/bot/human),
  │     content_type (text/audio/image/video/document/mixed),
  │     content_text, intent_id (nullable, FK),
  │     matched_via (regex/llm/exact/fallback),
  │     llm_tokens_used, latency_ms,
  │     feedback (none/good/bad), feedback_note,
  │     ts
  │
  ├── message_attachments
  │     id, message_id (FK), media_type, direction,
  │     storage_path, mime_type, size_bytes,
  │     duration_seconds, external_url,
  │     channel_specific_id, transcript, vision_description,
  │     thumbnail_path, created_at
  │
  ├── feedback_tickets
  │     id, tenant_id, type (bad_response/new_intent/
  │     edit_response/free_text),
  │     related_message_id, related_intent_id,
  │     proposed_text, proposed_keywords, reason, note,
  │     status (pending/approved/rejected), created_at,
  │     resolved_at, resolved_by
  │
  ├── handoff_events
  │     id, conversation_id, rule, triggered_at,
  │     notified_human_contact, resolved_at, resolution_note
  │
  ├── handoff_rules (configurable por tenant y por modo)
  │     id, tenant_id, mode (autonomous/assisted/hybrid),
  │     rule_code (H01..H07), trigger_intent,
  │     is_active, priority, notify_channel,
  │     notify_target, custom_message
  │     (Cada tenant puede sobrescribir los triggers
  │      H01-H07 por modo. Ej: en Modo A, H01 se
  │      dispara con "cliente dice listo para pagar",
  │      en Modo B con "cliente dio nombre + fecha".)
  │
  ├── availability_sources (uno por tenant, en Modo A/C)
  │     id, tenant_id, source_type (local_table/
  │     google_calendar/ical_url/mcp_server),
  │     credentials (jsonb, encrypted: oauth tokens,
  │       api keys, etc.),
  │     config (jsonb: calendar_id, slot_duration_min,
  │       buffer_min, timezone, sync_interval_min),
  │     last_sync_at, sync_status, is_active
  │
  ├── availability_slots (cache local de slots, opcional)
  │     id, tenant_id, source_id (FK),
  │     slot_date, slot_start, slot_end,
  │     is_blocked, block_reason, reservation_id (nullable),
  │     synced_at
  │     (Se llena desde la fuente externa en cada sync.
  │      El bot consulta esta tabla, no la API externa
  │      directamente, para baja latencia.)
  │
  ├── reservations
  │     id, tenant_id, conversation_id (FK),
  │     customer_name, customer_id_number, customer_phone,
  │     service_type, reserved_date, reserved_slot_id (FK),
  │     num_people, combo, total_amount, currency,
  │     status (tentative/pending_payment/confirmed/
  │             cancelled_by_user/cancelled_auto/
  │             cancelled_by_human),
  │     pre_reserved_by (bot/user), pre_reserved_at,
  │     payment_proof_message_id (FK, nullable),
  │     payment_confirmed_by_human (FK a users, nullable),
  │     payment_confirmed_at,
  │     handoff_at, cancelled_at, cancel_reason,
  │     notes (jsonb), created_at, updated_at
  │
  ├── audit_log
  │     id, tenant_id, actor, action, resource_type,
  │     resource_id, changes (jsonb), ts
```

### Índices importantes

- `messages(conversation_id, ts)` — para ventana de memoria
- `conversations(tenant_id, in_handoff, handoff_expires_at)` —
  para check de pausa
- `conversations(external_thread_id, channel_id)` — para lookup
  rápido
- `kb_intents(tenant_id, status)` — solo activas por tenant
- `media_assets(storage_path)` — para job de limpieza
- `media_assets(expires_at)` WHERE expires_at IS NOT NULL
- `availability_slots(tenant_id, slot_date)` — para check rápido
- `reservations(tenant_id, reserved_date)` — para evitar doble
  reserva
- `reservations(conversation_id)` — para lookup desde chat
- `handoff_rules(tenant_id, mode, is_active)` — para resolver
  el trigger correcto según el modo del tenant

---

## 6. Mensaje universal (normalización entrada/salida)

### Por qué

Cualquier canal (Wa, Tg, Web) llega con su propio formato. El
núcleo del bot no debe saber de canales. El mensaje se normaliza
a una estructura común, se procesa, y se vuelve a formatear al
salir.

### Mensaje de entrada (InboundMessage)

```python
class InboundMessage(BaseModel):
    tenant_id: UUID
    channel: Literal["whatsapp", "whatsapp_unofficial",
                     "telegram", "webchat"]
    external_id: str  # phone, chat_id, etc.
    thread_id: str
    user: UserRef  # external_id, name
    content: MessageContent
    timestamp: datetime
    raw: dict  # payload original del canal

class UserRef(BaseModel):
    external_id: str
    name: str | None

class MessageContent(BaseModel):
    type: Literal["text", "audio", "image", "video",
                  "document", "mixed"]
    text: str | None
    audio_url: str | None
    audio_duration: int | None
    image_url: str | None
    video_url: str | None
    document_url: str | None
    document_name: str | None
```

### Mensaje de salida (OutboundMessage)

```python
class OutboundMessage(BaseModel):
    tenant_id: UUID
    channel: str
    thread_id: str
    reply_to: str | None  # message_id externo al que responde
    content: OutboundContent

class OutboundContent(BaseModel):
    type: Literal["text", "audio", "image", "video",
                  "document", "mixed"]
    text: str | None
    audio_id: UUID | None  # FK a media_assets
    image_ids: list[UUID]
    video_id: UUID | None
    document_id: UUID | None
    tts: TTSConfig | None  # si None, usa audio_id directo

class TTSConfig(BaseModel):
    generate: bool
    voice_variant: str  # warm_1, warm_2, energetic, calm
    speed: float = 1.0
    use_cache: bool = True
```

### Envío nativo multimedia (no forward)

Todos los adapters DEBEN usar el método nativo de envío de
media del canal. Nunca `forwardMessage` ni equivalente.

- **Wa oficial**: POST `/messages` con `type: "image"` y
  `image: { link, caption }`
- **Baileys**: `sock.sendMessage(jid, { image: {...}, caption })`
- **Telegram**: `bot.send_photo(chat_id, photo, caption)`
- **Webchat**: render propio con URL directa

---

## 7. Sistema multi-canal (adapters)

### Interface común

```python
class ChannelAdapter(Protocol):
    async def parse_inbound(self, payload: bytes,
                            headers: dict) -> InboundMessage: ...
    async def send(self, message: OutboundMessage) -> SendResult: ...
    async def send_typing(self, thread_id: str) -> None: ...
    async def download_media(self,
                             media_ref: str) -> bytes: ...
    async def verify_webhook(self,
                             payload: bytes,
                             signature: str) -> bool: ...
```

### Implementación por canal

| Canal                | Lib                          | Notas                      |
|----------------------|------------------------------|----------------------------|
| WhatsApp oficial     | Meta Cloud API SDK           | Templates pre-aprobados    |
| WhatsApp no oficial  | Microservicio Node + Baileys | Riesgo ban, sesión QR      |
| Telegram             | python-telegram-bot (async)  | Polling o webhook          |
| Webchat              | Custom (FastAPI + WS)        | Widget embebible           |

### Decisión de canales por tenant

En el panel admin, el tenant tiene una lista de canales
disponibles según su plan. Activa/desactiva individualmente.

Cada canal tiene credenciales en `channels.credentials`
(jsonb, cifrado en reposo).

---

## 8. Sistema multi-LLM (agnóstico)

### Interface

```python
class LLMProvider(Protocol):
    async def chat(self, messages: list[Message],
                   tools: list[Tool] | None = None,
                   **kwargs) -> LLMResponse: ...
    async def transcribe(self, audio: bytes,
                         mime: str) -> str: ...
    async def synthesize_speech(self, text: str,
                                voice: str) -> bytes: ...
    async def analyze_image(self, image: bytes,
                            prompt: str) -> str: ...
    def get_capabilities(self) -> ModelCapabilities: ...
```

### Adapters

| Provider       | Estado     | Notas                            |
|----------------|------------|----------------------------------|
| MiniMax        | Sprint 1   | Tu modelo, 12B, multimodal       |
| OpenAI-compat  | Sprint 2   | Cualquier provider compatible    |
| Anthropic      | Sprint 3+  | Si se requiere                   |
| Local Whisper  | Sprint 1   | Fallback STT                     |

### Router por tenant

Cada tenant tiene UN provider activo (con prioridad para
failover opcional). El `LLMRouter` lee la config del tenant
y devuelve el adapter correcto.

```python
class LLMRouter:
    def get_provider(self, tenant_id: UUID) -> LLMProvider:
        config = self.llm_configs.get_active(tenant_id)
        return self._build(config)
```

### STT inteligente (multimodal vs dedicado)

```python
async def transcribe_audio(audio: bytes,
                           tenant_id: UUID) -> str:
    provider = router.get_provider(tenant_id)

    if provider.get_capabilities().audio_input:
        # El LLM hace todo (un solo roundtrip, mejor contexto)
        return await provider.transcribe(audio)
    else:
        # Fallback: STT dedicado
        fallback = get_stt_fallback(tenant_id)
        return await fallback.transcribe(audio)
```

Configuración en `llm_providers`:
- `capabilities.audio_input: bool` — si true, pasa audio al LLM
- `stt_fallback: {provider, model, endpoint}` — si no es multimodal

---

## 9. Clasificador híbrido

### Flujo de decisión

```
  Mensaje entrante normalizado
       │
       ▼
  ┌────────────────────────────────────┐
  │ 1. ¿Está en handoff activo?        │──Sí──▶ callar, log, notificar
  │    (ventana corta 12h configurable) │
  └────────┬───────────────────────────┘
       No  │
          ▼
  ┌────────────────────────────────────┐
  │ 2. ¿Está en handoff pero pasaron   │──Sí──▶ notificar humano,
  │    más horas (ventana larga 48h)?  │        NO responder al cliente
  └────────┬───────────────────────────┘
       No  │
          ▼
  ┌────────────────────────────────────┐
  │ 3. ¿Pasó la ventana de retomar     │──Sí──▶ retomar bot
  │    (ej. >48h)? Retoma bot.         │
  └────────┬───────────────────────────┘
       No (caso raro) │
                    ▼
  ┌────────────────────────────────────┐
  │ 4. Anti-inyección (3 capas)        │
  │    (reutilizar lógica de Green     │
  │    Glamping)                       │
  └────────┬───────────────────────────┘
          │
          ▼
  ┌────────────────────────────────────┐
  │ 5. ¿Match con KB por regex?        │──Sí──▶ respuesta canned
  │    (carga KB del tenant, prueba    │        + adjuntos
  │    keywords_regex de cada intent)  │
  └────────┬───────────────────────────┘
       No  │
          ▼
  ┌────────────────────────────────────┐
  │ 6. ¿Match fuzzy / semántico?       │──Sí──▶ respuesta KB
  │    (embeddings, opcional, V2)      │
  └────────┬───────────────────────────┘
       No  │
          ▼
  ┌────────────────────────────────────┐
  │ 7. LLM clasifica intent            │──Sí──▶ busca respuesta en KB
  │    (rápido, structured output)     │
  └────────┬───────────────────────────┘
       No  │
          ▼
  ┌────────────────────────────────────┐
  │ 8. LLM genera respuesta libre      │──Sí──▶ respuesta generada
  │    (más lento, más caro)           │
  └────────┬───────────────────────────┘
          │
          ▼
  ┌────────────────────────────────────┐
  │ 9. ¿Dispara handoff?               │──Sí──▶ marcar handoff +
  │    (reglas H01-H07)                │        notificar humano
  └────────┬───────────────────────────┘
          │
          ▼
  ┌────────────────────────────────────┐
  │ 10. Decidir formato de salida      │
  │     (texto / audio / imagen / mix) │
  │     y generar                      │
  └────────┬───────────────────────────┘
          │
          ▼
  ┌────────────────────────────────────┐
  │ 11. Log + métricas + feedback      │
  └────────────────────────────────────┘
```

### Optimizaciones

- 90% de mensajes caen en paso 5 (regex match) — sin LLM
- 8% caen en paso 7 (LLM clasifica) — 1-2s
- 2% caen en paso 8 (LLM genera) — 2-4s
- Latencia objetivo total: <2s para paso 5, <5s para paso 7+

### Cache de clasificaciones

Cachear en Redis: `text_hash → intent_id` por tenant.
TTL: 24h. Hit ratio esperado: 30-50% (mensajes repetidos).

### Árbol de decisión por modo de operación

El clasificador bifurca según `tenant.operation_mode`. Los
primeros 4 pasos (handoff, anti-inyección) son comunes. A
partir del paso 5, el comportamiento diverge.

```
                          ┌──────────────┐
                          │  Mensaje     │
                          │  entrante    │
                          └──────┬───────┘
                                 │
                          [Pasos 1-4 comunes]
                                 │
                          ¿Modo del tenant?
                                 │
            ┌────────────────────┼────────────────────┐
            ▼                    ▼                    ▼
      ┌──────────┐         ┌──────────┐         ┌──────────┐
      │ Modo A   │         │ Modo B   │         │ Modo C   │
      │autónomo  │         │asistido  │         │ híbrido  │
      └────┬─────┘         └────┬─────┘         └────┬─────┘
           │                    │                    │
           ▼                    ▼                    ▼
  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
  │ 5A. Match KB    │   │ 5B. Match KB    │   │ 5C. Match KB    │
  │ 6A. Validar     │   │ 6B. ¿Intención  │   │ 6C. ¿El intent  │
  │     disponib.   │   │     de compra?  │   │     requiere    │
  │ 7A. Confirmar  │   │ 7B. Si SÍ:      │   │     humano?     │
  │     pre-reserva │   │     handoff     │   │ 7C. Si SÍ:      │
  │ 8A. Handoff     │   │     temprano    │   │     handoff     │
  │     solo pago   │   │     (H01)      │   │ 8C. Si NO:      │
  └─────────────────┘   │ 8B. Si NO:      │   │     comportate   │
                        │     cierre      │   │     como Modo A │
                        │     elegante    │   └─────────────────┘
                        └─────────────────┘
```

#### Detalle por modo

**Modo A — autónomo**

```
  5A. Match KB
       │
       ▼
  6A. ¿Mensaje menciona fecha?
       │
       ├── NO  → respuesta normal
       │
       └── SÍ
            │
            ▼
       ┌──────────────────────────────┐
       │ Consultar disponibilidad     │
       │ (AvailabilityProvider)       │
       │ check_is_available(date)     │
       └──────────┬───────────────────┘
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
   DISPONIBLE         NO DISPONIBLE
        │                   │
        ▼                   ▼
   Bot: "¡El 14 de       Bot: "El 14 no hay
   junio hay disponib.   disponibilidad 😔
   ¿Lo reservo?"         ¿Te sirve el 15 o 21?"
        │                   │
        ▼                   ▼
   7A. ¿Cliente confirma?
        │
        ├── NO  → cierre elegante
        │         (no insistir, no perseguir)
        │
        └── SÍ
             │
             ▼
        Bot: "Listo, te pre-reservo.
              Te paso con mi compañera
              para el tema de pago 🙌"
             │
             ▼
        Handoff (H01) — solo para pago
        [conversations.state = ready_for_payment]
        [reservations.status = tentative]
```

**Modo B — asistido**

```
  5B. Match KB
       │
       ▼
  6B. ¿Intención de compra detectada?
       (keywords: reservar, agendar, separar,
        quiero, cuánto cuesta, combo X, fecha Y)
       │
       ├── NO  → respuesta normal
       │         (información,闲聊, etc.)
       │
       └── SÍ
            │
            ▼
       Bot: "¡Perfecto! Te paso con mi
             compañera, ella te ayuda con
             disponibilidad, datos y pago 🙌"
            │
            ▼
       Handoff (H01) — temprano
       [conversations.state = in_handoff]
       (El humano hace TODO el resto)
```

**Modo C — híbrido**

```
  5C. Match KB
       │
       ▼
  6C. ¿El intent requiere humano?
       (configurado por tenant: lista de
        intents, servicios o keywords que
        fuerzan handoff)
       │
       ├── NO  → comportate como Modo A
       │         (validar disponibilidad,
       │          confirmar, handoff solo pago)
       │
       └── SÍ
            │
            ▼
       Bot: "Esto lo maneja directamente
             mi compañera, te la paso 🙌"
            │
            ▼
       Handoff (H01) — temprano
       (como Modo B)
```

#### Cierre elegante (cualquier modo)

Cuando el bot detecta que el cliente solo preguntó pero no
compra (no confirma reserva, no da datos, no pregunta por
precio concreto), cierra sin insistir:

```
  Disparadores de cierre elegante:
  - "solo preguntaba"
  - "ah ok, gracias"
  - "luego miro"
  - silencio > X minutos tras info
  - cambiar tema
  - despedida explícita

  Bot: "¡Perfecto! Cuando quieras volver,
        aquí estaré 🌿"
  (NO insiste, NO manda publicidad, NO
   hace seguimiento agresivo)
```

#### Configuración por intent (Modo C)

La tabla `kb_intents` añade un campo:

```
  requires_human: bool
  human_reason: str | None  # "evento corporativo",
                              # "paquete personalizado",
                              # "precio fuera de catálogo"
```

Si `requires_human = true` → ese intent siempre va a
handoff, sin importar el modo del tenant.

---

## 10. Sistema TTS con cache y promoción

### Voz

- Una voz clonada fija por tenant (configurada en panel)
- Variantes: `warm_1`, `warm_2`, `energetic`, `calm`
  (anti-monotonía, rotación determinística o aleatoria)
- Almacenada en el provider TTS del tenant (MiniMax tiene TTS)

### Decisión de TTS

```python
def should_use_tts(text: str,
                   intent_id: UUID,
                   tenant_config) -> TTSConfig:
    if intent_id and has_pregenerated_audio(intent_id):
        return TTSConfig(generate=False)  # usa pregrabado

    if len(text) < tenant_config.tts_min_chars:
        return TTSConfig(generate=False)  # texto corto

    return TTSConfig(
        generate=True,
        voice_variant=pick_variant(intent_id),  # rotación
        speed=1.0
    )
```

### Cache de TTS

Tabla `tts_cache`:
- `text_hash` (sha256)
- `text_content`
- `audio_id` (FK a media_assets)
- `use_count` (incrementa en cada uso)
- `status` ("auto" | "promoted")
- `created_at`, `last_used_at`

Lógica:
1. Generar TTS → guardar en `tts/` y registrar en `tts_cache`
2. Si llega mismo texto otra vez → servir desde cache
3. Si `use_count > N` (config, default 5) → marcar como candidato
4. Panel admin muestra candidatos a promover
5. Si se aprueba → mover a `pregenerated/`, queda como predeterminado

### Variación de voz

- Por tenant: define las variantes disponibles (de 1 a N)
- Algoritmo de elección:
  - Si solo 1 variante: usar siempre
  - Si N variantes: round-robin por turno
  - Override por intent: el admin puede fijar variante

---

## 11. Handoff inteligente con ventanas

### Estados de una conversación

```
  ┌──────────┐
  │  ACTIVE  │ ← estado normal, bot responde
  └────┬─────┘
       │ trigger H01-H07
       ▼
  ┌──────────────┐
  │ IN_HANDOFF   │ ← humano atendiendo
  └────┬─────────┘
       │ resolución manual
       ▼
  ┌──────────┐
  │  ACTIVE  │
  └──────────┘
```

### Lógica de "callar inteligente"

```
  Mensaje entrante
       │
       ▼
  ¿Handoff activo? (handoff_expires_at > NOW())
       │
       ├── NO  ──▶ flujo normal del bot
       │
       └── SÍ
            │
            ├── ¿Hace cuánto del handoff?
            │     │
            │     ├── < ventana_pausa_corta (12h)
            │     │    → NO responder
            │     │    → Reenviar mensaje al humano
            │     │
            │     ├── ventana_pausa_corta a ventana_pausa_larga (12-48h)
            │     │    → NO responder
            │     │    → Reenviar + alertar "cliente insiste"
            │     │
            │     └── > ventana_pausa_larga (48h)
            │          → Retomar bot
            │          → Reset handoff_expires_at
            │          → Log: "bot retomó después de X horas"
            │
            └── (registrar siempre en messages)
```

### Configuración por tenant

```yaml
# tenant.handoff_config
pausa_corta_horas: 12        # bot calla
pausa_larga_horas: 48        # calla + alerta
ventana_retomar_horas: 48    # bot retoma (>= pausa_larga)
contacto_humano: "+573178067766"
canal_notificacion_humano: "telegram"
```

### Notificación al humano

Al disparar handoff, push al canal configurado (Telegram, SMS, email):
```
  🔔 HANDOFF H01 - Green Glamping
  👤 Juan Pérez (+57 312 555 1234)
  💬 "Mi nombre es Juan Pérez, CC 1234567890, combo 5"
  📅 14 junio
  🔗 [Abrir conversación]
```

### Triggers de handoff por modo

La tabla `handoff_rules` permite configurar umbrales
distintos por modo y por tenant. Defaults sugeridos:

| Regla | Modo A            | Modo B        | Modo C                    |
|-------|-------------------|---------------|---------------------------|
| H01   | "cliente confirma listo para pagar" | "cliente muestra intención de compra" | depends: H01-ModoA o H01-ModoB según intent |
| H02   | "hablar con humano" | "hablar con humano" | "hablar con humano" |
| H03   | queja             | queja         | queja                     |
| H04   | pedido descuento  | pedido descuento | pedido descuento     |
| H05   | servicio no catalogado | servicio no catalogado | servicio no catalogado |
| H06   | otro número       | otro número   | otro número               |
| H07   | 3 turnos sin clasificar | 3 turnos sin clasificar | 3 turnos sin clasificar |

**Diferencia clave**:
- **Modo A**: el bot hace casi todo, el humano solo valida
  pago. H01 es el ÚLTIMO paso, no el primero.
- **Modo B**: el bot solo filtra. H01 es el PRIMER paso
  cuando hay interés real.
- **Modo C**: depende. El árbol de decisión del clasificador
  (sección 9) elige qué H01 usar según si el intent
  `requires_human` o no.

---

## 12. Servidor y cliente MCP

### Multibot como servidor MCP

Otros agentes IA pueden invocar Multibot:

```
  Tools expuestas:
  - send_message(tenant_id, channel, thread_id, content)
  - get_conversation(tenant_id, thread_id)
  - classify_intent(tenant_id, text)
  - trigger_handoff(tenant_id, thread_id, reason)
  - list_active_conversations(tenant_id)
  - get_tenant_kb(tenant_id)

  Resources expuestas:
  - kb://{tenant_id}/intents
  - conversations://{tenant_id}/{thread_id}
  - metrics://{tenant_id}/summary
```

Endpoint: `mcp.multibot.co` (o path local `/mcp`).

### Multibot como cliente MCP

El bot puede consumir tools externas vía MCP:
- CRM (consultar datos del cliente)
- Calendar (verificar disponibilidad)
- Payment gateway (validar comprobantes)
- Inventario (verificar fechas disponibles)

Configuración en `tenant.mcp_clients` (lista de servidores MCP
con sus endpoints y credenciales).

### Caso de uso V1 (Sprint 3)

En V1, el foco es:
1. Exponer Multibot como servidor MCP (bajo costo, alto valor
   para integraciones con Claude Desktop, n8n, etc.)
2. El cliente MCP externo se implementa con un servidor mock
   para desarrollo
3. Integraciones reales (CRM, calendar) se hacen caso a caso

---

## 13. Emulador / decisor (sandbox)

### Modo simulación

Endpoint: `POST /admin/simulate`

```json
{
  "tenant_id": "uuid",
  "thread_id": "sim_001",
  "user_message": "Hola, cuánto cuesta el combo 5?",
  "user_external_id": "sim_user",
  "context": {
    "is_first_contact": false,
    "conversation_history": []
  }
}
```

### Salida

```json
{
  "decision_tree": [
    {"step": 1, "check": "in_handoff?", "result": "no",
     "elapsed_ms": 2},
    {"step": 2, "check": "anti_injection", "result": "pass",
     "elapsed_ms": 1},
    {"step": 3, "check": "kb_regex_match",
     "result": "matched", "intent": "info_combos",
     "candidates": 4, "winner_score": 0.92,
     "elapsed_ms": 8},
    {"step": 4, "check": "handoff_trigger", "result": "no",
     "elapsed_ms": 1},
    {"step": 5, "check": "output_format",
     "decision": "text+image", "elapsed_ms": 3}
  ],
  "response": {
    "type": "mixed",
    "text": "...",
    "image_ids": ["uuid1", "uuid2"]
  },
  "metrics": {
    "total_latency_ms": 15,
    "llm_tokens": 0,
    "llm_calls": 0,
    "cost_usd": 0
  }
}
```

### Visualización en panel

El panel renderiza el árbol de decisión con cajas y flechas,
permitiendo:
- Debug en producción sin tocar el bot real
- Onboarding de clientes mostrando cómo responde
- Exportar cada simulación como test case (pytest)

### Tests reproducibles

Botón "Exportar como test" → genera archivo pytest con:
```python
async def test_saludo_mañana():
    sim = Simulator(tenant="green_glamping")
    result = await sim.run("Hola, buenos días")
    assert result.matched_intent == "saludo_puro"
    assert "mañana" in result.response_text.lower()
    assert result.metrics["llm_calls"] == 0
```

---

## 14. Panel admin wizard

### Stack

- FastAPI sirve las rutas admin
- Jinja2 renderiza templates
- HTMX para interactividad (sin escribir JS a mano)
- CSS custom con tema limpio (paleta verde/azul, sin framework
  de UI pesado)

### Wizard de primer tenant (6 pasos)

```
  Paso 1: Datos básicos
  ├─ Nombre del negocio
  ├─ Slug
  ├─ Logo (subir)
  └─ Zona horaria

  Paso 2: Modo de operación  ← NUEVO
  ├─ ¿Quién gestiona las reservas?
  │   ○ Bot gestiona todo (Modo A)
  │     - El bot valida disponibilidad y confirma
  │     - Humano solo valida el pago
  │     - Requiere: configurar calendario
  │
  │   ○ Humano gestiona (Modo B)
  │     - Bot filtra y prepara el contexto
  │     - Humano hace todo lo demás
  │     - Requiere: solo configurar humano
  │
  │   ○ Híbrido (Modo C, recomendado)
  │     - Bot gestiona lo rutinario
  │     - Ciertos servicios van directo a humano
  │     - Requiere: configurar calendario + lista de intents
  │       que requieren humano
  │
  └─ [Vista previa del flujo según modo elegido]

  Paso 3: Conectar canal
  ├─ Elegir tipo: Wa oficial / no oficial / Tg / web
  ├─ Pegar credenciales (con validación inline)
  └─ Probar conexión (botón "Enviar mensaje de prueba")

  Paso 4: Calendario / disponibilidad (solo Modo A y C)
  ├─ Fuente: ○ Tabla propia ○ Google Calendar ○ URL iCal
  │         ○ MCP server externo
  ├─ Configurar según fuente (OAuth Google, URL iCal, etc.)
  ├─ Definir duración de slot (ej. 60 min)
  ├─ Definir buffer entre reservas (ej. 30 min)
  ├─ Probar: ¿qué slots hay disponibles el próximo mes?
  └─ (Si Modo B, este paso se salta)

  Paso 5: Subir assets iniciales
  ├─ Imágenes de portafolio (drag & drop)
  ├─ Audios pre-grabados (drag & drop)
  └─ Documentos PDF (drag & drop)

  Paso 6: Cargar base de conocimiento + probar bot
  ├─ Subir JSON/JSONL
  ├─ Vista previa de intents detectados
  ├─ Marcar intents que requieren humano (Modo C)
  ├─ Simulador embebido (modo sandbox)
  ├─ Mensaje de prueba al canal real (opt-in)
  └─ Confirmar activación
```

### Pantallas principales (post-setup)

| Pantalla              | Contenido                              |
|-----------------------|----------------------------------------|
| Dashboard             | Métricas, conversaciones activas       |
| Conversaciones        | Lista + detalle + intervenir          |
| Base de conocimiento  | Intents, keywords, respuestas          |
| Canales               | Activar/desactivar, credenciales      |
| LLM                   | Provider, modelo, capacidades, API key |
| Voz (TTS)             | Variantes, audios pre-grabados         |
| Handoffs              | Reglas, humano asignado, ventanas      |
| Retroalimentación     | Tickets pendientes, aprobar/rechazar   |
| Métricas              | Volumen, latencia, intents top, etc.   |
| Simulador             | Sandbox para probar sin producción     |

### Permisos

- Admin: acceso total
- Viewer: solo lectura + métricas
- (No hay multi-usuario por tenant en MVP)

---

## 15. Retroalimentación del cliente

### 4 canales de feedback

**A) Marcar respuestas (en vista de conversaciones)**
```
  [✓ OK]  [✗ Está mal]  [📝 Editar]

  → Crea feedback_ticket tipo "bad_response"
```

**B) Sugerir nuevos intents (en sección KB)**
```
  [+ Nuevo Intent]
  Nombre, keywords, respuesta, handoff
  Estado: BORRADOR
  → Crea feedback_ticket tipo "new_intent"
```

**C) Editar respuestas existentes**
```
  Click en intent → modo edición
  Cambios: status "pending_approval"
  → Crea feedback_ticket tipo "edit_response"
```

**D) Reporte libre**
```
  [📝 Comentario / sugerencia]
  Texto libre
  → Crea feedback_ticket tipo "free_text"
```

### Workflow de aprobación

```
  Cliente sugiere
       │
       ▼
  ┌──────────────┐
  │   PENDING    │
  └──────┬───────┘
         │
    ┌────┴─────┐
    ▼          ▼
  APPROVED  REJECTED
    │          │
    ▼          ▼
  ACTIVO    Notificar al cliente
  (en KB)   por qué no
```

Tickets aparecen en el panel admin → tú los revisas y decides.

### Métricas de feedback

- Tiempo promedio de resolución
- % de sugerencias aprobadas vs rechazadas
- Intents con más "está mal" (candidatos a reescribir)

---

## 16. Plan host → Docker + política de archivos

### Estructura de directorios

```
plataforma-multibot/
├── app/                  # código Python
│   ├── core/
│   ├── models/           # SQLAlchemy
│   ├── schemas/          # Pydantic
│   ├── db/
│   ├── channels/         # adapters
│   ├── llm/              # adapters LLM
│   ├── bot/              # cerebro
│   ├── admin/            # panel
│   └── api/              # webhooks
├── workers/              # ARQ
├── tests/
├── data/                 # TODO archivo no-código
│   ├── media/
│   │   ├── received/     # entrada (90d)
│   │   ├── sent/
│   │   │   ├── portfolio/    # ∞
│   │   │   ├── pregenerated/ # ∞
│   │   │   ├── kb_assets/    # ∞
│   │   │   ├── tts/          # rotación
│   │   │   └── temp/         # 24h
│   │   ├── thumbnails/   # regenerables
│   │   └── quarantine/   # 7d antes de hard delete
│   ├── exports/
│   │   ├── db_dumps/     # 30d
│   │   ├── conversation_logs/ # 90d
│   │   └── reports/      # 365d
│   ├── seeds/            # versionado
│   └── uploads/tenants/
├── docker-compose.yml
├── Dockerfile
├── .env.example
└── README.md
```

### Política de retención y eliminación

| Tipo                | Retención  | Acción al expirar                  |
|---------------------|------------|------------------------------------|
| `received/*`        | 90 días    | soft delete → quarantine 7d → hard |
| `sent/portfolio/*`  | ∞          | nunca                              |
| `sent/pregenerated/` | ∞          | nunca                              |
| `sent/kb_assets/*`  | ∞          | nunca                              |
| `sent/tts/*`        | 30-60 días | si use_count<3 a 30d, si no a 60d  |
| `sent/temp/*`       | 24 horas   | hard delete directo                |
| `quarantine/*`      | 7 días     | hard delete (manual con confirma)  |
| `exports/db_dumps/` | 30 días    | rotación, mantener últimos 5       |
| `exports/logs/`     | 90 días    | rotación                           |
| `exports/reports/`  | 365 días   | rotación anual                     |
| `thumbnails/*`      | ∞ (regen)  | se pueden borrar si >1 año         |

**Configurable por tenant**: `retention_days` (60/90/180/365).

### Seguridad de eliminación

1. Job nocturno (ARQ scheduler, 3 AM) escanea `data/`
2. Para cada archivo candidato:
   - Si está referenciado en BD → mover a `quarantine/`
   - Si huérfano → mover a `quarantine/`
3. Job siguiente (7 días después) hace hard delete de quarantine
4. `/quarantine/` no se limpia automáticamente; solo manual
5. Log de todo lo eliminado (auditoría)

### Plan host → Docker

**Fase 1 (desarrollo)**: todo en host
- Postgres en container existente (ya levantado)
- Multibot corre con `uvicorn app.main:app --reload`
- Workers corren en terminales separadas
- Archivos multimedia en `./data/`

**Fase 2 (deploy piloto)**: docker-compose
- Multibot web en container
- Multibot worker en container
- Redis en container
- Postgres se queda en container existente
- Volumen `./data` montado
- nginx reverse proxy

**Fase 3 (multi-cliente)**: misma infra, más tenants
- Sin cambios estructurales
- Solo más filas en `tenants`
- Backups automatizados con cron + pg_dump

---

## 16b. Roadmap por sprints (orden de construcción)

### Sprint 0: Skeleton (1-2 semanas)
- Setup proyecto, pyproject.toml, estructura dirs
- SQLAlchemy models + Alembic
- FastAPI app básica con healthcheck
- Docker-compose
- Primer modelo `Tenant` + crear primer tenant de prueba
- Conexión al Postgres existente

### Sprint 1: Green Glamping funcional (2-3 semanas)
- Cargar KB de Green Glamping desde `data/seeds/`
- Clasificador regex (paso 5 del árbol de decisión)
- Adapter Telegram (migrar bot actual de n8n)
- Handoff básico con pausa
- Memoria últimos 10 turnos (Redis)
- Tests del clasificador con datos de Green Glamping

### Sprint 2: Panel admin visual (2-3 semanas)
- Wizard de 5 pasos para nuevo tenant
- Pantalla KB (CRUD de intents)
- Pantalla conversaciones (lista + detalle)
- HTMX para interactividad
- Simulador básico (sin árbol de decisión todavía)

### Sprint 3: Multi-canal + LLM agnóstico (2-3 semanas)
- Adapter WhatsApp oficial
- Microservicio Node + Baileys (no oficial)
- LLM interface + adapter MiniMax
- Router por tenant
- STT inteligente (multimodal vs fallback)
- Emulador completo con árbol de decisión visual

### Sprint 4: TTS + retroalimentación + MCP (2-3 semanas)
- TTS con voz clonada
- Cache de TTS
- Promoción automática a predeterminado
- Sistema de retroalimentación del cliente
- Servidor MCP (tools expuestas)
- Job nocturno de limpieza

### Sprint 5: Pulido + métricas + voz salida (2-3 semanas)
- Métricas y dashboard
- TTS con variantes de voz
- Fuzzy matching / embeddings (V2)
- Cliente MCP (consumir externos)
- Documentación para handover

---

## 17. Ciclo completo de reserva (bot → humano → pago)

Esta sección cubre el flujo de extremo a extremo: desde que el
cliente muestra intención de reservar hasta que confirma el pago
y queda registrado. **El flujo varía según el modo de operación
del tenant** (ver sección 1).

### Mapa de modos vs flujo de reserva

```
                    ┌─────────────┐
                    │  ¿QUIÉN     │
                    │  GESTIONA?  │
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   ┌─────────┐        ┌─────────┐        ┌─────────┐
   │ Modo A  │        │ Modo B  │        │ Modo C  │
   │autónomo │        │asistido │        │ híbrido │
   └────┬────┘        └────┬────┘        └────┬────┘
        │                  │                  │
        ▼                  ▼                  ▼
   Bot valida         Bot NO valida      Por intent:
   disponibilidad     disponibilidad      si requiere_human
        │             ni confirma        → Modo B
        ▼             nada               si NO requiere_human
   Bot confirma       │                  → Modo A
   pre-reserva        ▼                  │
        │            Bot detecta              │
        ▼            intención →               ▼
   Handoff SOLO       Handoff           "Mejor de los dos mundos"
   para pago          temprano               │
   (humano solo       (humano hace      ┌────┴────┐
   valida pago)       TODO)             Modo A    Modo B
                                          │         │
                                          ▼         ▼
                                       Valida    Handoff
                                       disponib. temprano
                                       + confirma
                                       + handoff
                                       solo pago
```

### Estados de la conversación

```
  ┌──────────┐
  │  ACTIVE  │ ← conversación normal, bot responde
  └────┬─────┘
       │ trigger H01-H07 (umbral depende del modo)
       ▼
  ┌──────────────┐
  │ IN_HANDOFF   │ ← humano interviniendo
  └────┬─────────┘
       │ En Modo A/C: humano marca "lista para pago"
       │ En Modo B: humano cierra todo el ciclo
       ▼
  ┌─────────────────────┐
  │ READY_FOR_PAYMENT   │ ← bot espera comprobante
  └────┬────────────────┘
       │ bot recibe imagen (comprobante) o texto
       ▼
  ┌──────────────────┐
  │ AWAITING_PROOF   │ ← en cola de validación humana
  └────┬─────────────┘
       │ validado OK
       ▼
  ┌──────────────┐
  │  CONFIRMED   │ ← reserva confirmada, enviar detalle
  └────┬─────────┘
       │ ack del cliente
       ▼
  ┌──────────┐
  │  CLOSED   │
  └──────────┘
```

### Flujo por modo

#### MODO A — Bot gestiona todo (autónomo)

El bot valida disponibilidad, confirma pre-reserva, hace
handoff SOLO para validación de pago. El humano solo valida
el comprobante.

```
  [1] Cliente saluda
  [2] Pregunta por combo (regex: info_combos)
  [3] Bot responde con info del combo + portafolio
  [4] Cliente da fecha
  [5] Bot consulta availability_sources (Google Calendar
      o tabla local)
  [6] ¿Disponible?
       ├── SÍ → Bot: "¡El 14 hay disponibilidad! ¿Lo reservo?"
       │            [reservations.status = tentative,
       │             reserved_slot_id = slot_id]
       │
       ├── NO → Bot: "El 14 no hay 😔 ¿Te sirve el 15 o 21?"
       │           [NO crea reservation]
       │
       └── Dudoso → Bot escala a humano (H02)
  [7] Cliente confirma ("sí, listo" / "dale")
       │
       ├── SÍ → Bot: "Listo, te pre-reservo. Te paso con
       │           mi compañera para el tema de pago 🙌"
       │       [H01 triggered, H01-ModoA]
       │       [conversations.state = "ready_for_payment"]
       │       [handoff_expires_at = NOW() + 24h]
       │
       └── NO → Cierre elegante:
                  Bot: "Perfecto, cuando quieras volver
                        aquí estaré 🌿"
                  [NO reservation, NO handoff]
  [8] Humano (Johana) valida el pago (ver pasos 4-8 comunes)
  [9] Bot envía confirmación final
  FIN
```

#### MODO B — Humano gestiona (asistido)

El bot solo filtra y prepara contexto. El humano hace todo:
disponibilidad, confirmación, datos de pago, cierre.

```
  [1] Cliente saluda
  [2] Pregunta por combo (regex: info_combos)
  [3] Bot responde con info del combo + portafolio
  [4] Cliente da fecha / muestra intención de compra
      (keywords: reservar, agendar, cuánto, combo X, fecha Y)
  [5] Bot: "¡Perfecto! Te paso con mi compañera,
            ella te ayuda con disponibilidad, datos y pago 🙌"
      [H01 triggered, H01-ModoB]
      [conversations.state = "in_handoff"]
      [handoff_expires_at = NOW() + 12h]
  [6] Johana interviene — ella hace TODO:
      - Valida disponibilidad en su calendario
      - Confirma con el cliente
      - Pide datos personales si faltan
      - Envía datos de pago desde su chat personal
      - Recibe comprobante
      - Confirma
  [7] Bot en pausa todo este tiempo
  FIN
```

#### MODO C — Híbrido (recomendado)

El bot gestiona lo rutinario (Modo A) excepto para intents
marcados como `requires_human = true` (Modo B para esos).

```
  [1] Bot clasifica intent
  [2] ¿El intent tiene requires_human = true?
       ├── NO  → Comportate como Modo A
       │         (valida disponibilidad, confirma,
       │          handoff solo pago)
       │
       └── SÍ → Comportate como Modo B
                 (handoff temprano, humano hace todo)
```

**Ejemplo Modo C** (Green Glamping):
- `info_combos` → Modo A (bot confirma pre-reserva)
- `reserva_evento_corporativo` (custom) → Modo B
  (humano hace todo porque requiere negociación)
- `pedido_descuento` (H04) → Modo B
  (humano evalúa la firmeza, no el bot)

### Pasos comunes a Modo A y C (post-handoff)

Estos pasos son iguales independientemente del modo. La
diferencia es **cuándo** se hace el handoff.

#### Paso 1: Handoff estándar (H01)

```
  Bot: "Recibido ✅. Te paso con mi compañera para
        finalizar. Ella te escribe en un momento 🙌"

  [H01 triggered]
  [conversations.state = "ready_for_payment"  (en Modo A/C)]
  [conversations.state = "in_handoff"        (en Modo B)]
  [conversations.handoff_rule = "H01"]
  [conversations.handoff_expires_at = NOW() + 12h (Modo B)
                                        o + 24h (Modo A/C)]
  [Push a Johana: contexto completo]
```

#### Paso 2: Johana interviene (chat humano-humano)

Johana recibe la notificación push (Telegram/SMS). Ella habla
directamente con el cliente por el mismo canal (Wa/Tg), desde
su propio número/cuenta.

Durante este período:
- Bot en pausa (no responde)
- Mensajes del cliente se reenvían a Johana
- Johana puede pedir más datos, confirmar fechas, etc.

En **Modo B**, Johana hace TODO: disponibilidad, datos,
envío de info de pago, validación.

En **Modo A/C**, Johana solo gestiona el pago: verifica
comprobante y confirma.

#### Paso 3: Johana marca "lista para pago" en el panel (Modo A/C)

En **Modo A/C**, cuando Johana verifica el comprobante
(porque el cliente ya recibió los datos de pago del bot),
abre la conversación en el panel admin y marca:

```
  ┌────────────────────────────────────────────────────┐
  │  Conversación con Juan Pérez                       │
  │  ─────────────────────────────────────────────     │
  │  Estado actual: AWAITING_PROOF                     │
  │                                                    │
  │  Comprobante: [imagen adjunta]                     │
  │  Monto: $200.000 ✓                                 │
  │  Referencia: 1234567                               │
  │                                                    │
  │  [ ✓ Pago confirmado ]                             │
  │  [ ✗ Pago no recibido / monto incorrecto ]        │
  │  [ 💬 Continuar chateando yo ]                     │
  └────────────────────────────────────────────────────┘
```

Al confirmar:
1. `conversations.state = CONFIRMED`
2. `reservations.status = CONFIRMED`
3. `reservations.payment_confirmed_at = NOW()`
4. Bot envía al cliente: confirmación con detalles finales

#### Paso 4: Bot envía mensaje de pago (Modo A/C, automático)

En **Modo A/C**, el bot envía los datos de pago inmediatamente
después de que el cliente confirma "listo, voy a pagar". El
bot hace esto ANTES del handoff (porque el bot gestiona, el
humano solo valida).

**Estructura del mensaje de pago** (configurable por tenant):

```yaml
# tenants.payment_message_template (jsonb)
plantilla:
  texto_intro: "¡Todo listo, {nombre_cliente}! 🎉 Te dejo
                los datos para que puedas hacer el pago:"
  texto_datos: |
    🏦 *Nequi / Daviplata / Llave*
    📱 3124436880

    🏦 *Davivienda*
    💳 Cuenta de ahorros 488400301062
    👤 Jonathan García

    🏦 *BBVA*
    💳 0079209995
  texto_recordatorio: |
    Cuando hagas la transferencia, mándame el comprobante
    por acá mismo 📸. Si pasaron más de 24h sin pago, la
    reserva se libera automáticamente.
  texto_despedida: "¡Gracias por confiar en Green Glamping! 🌿"
  adjuntos:
    - tipo: imagen
      asset_id: qr_nequi_daviplata
      caption: "QR Nequi / Daviplata / Llave"
    - tipo: imagen
      asset_id: qr_davivienda
      caption: "QR Davivienda"
    - tipo: audio
      asset_id: explicacion_pasos_pago
      caption: ""  # audio pre-grabado explicativo
```

**El bot envía en orden** (mensajes nativos, no forward):
1. Texto introductorio
2. Imagen QR 1
3. Imagen QR 2
4. Texto con datos bancarios
5. Audio pre-grabado (opcional, explica pasos)
6. Texto recordatorio
7. Texto despedida

Después de enviar, el bot hace handoff (H01) para que Johana
valide el comprobante cuando llegue.

#### Paso 5: Cliente hace el pago

El cliente va a su app bancaria, hace la transferencia, y
regresa al chat con:

- Imagen del comprobante (caso más común, ~80%)
- Texto "listo, ya pagué" (a veces)
- Audio "ya hice la transferencia" (raro pero posible)

#### Paso 6: Bot recibe el comprobante (Modo A/C)

En **Modo B**, este paso no existe (Johana recibe directo).

En **Modo A/C**:
```
  Cliente: [envía imagen]
  Bot: [clasifica]
       │
       ├─ ¿Es comprobante? (clasificador con vision)
       │
       ├─ SÍ (alta confianza)
       │   → cambiar conversations.state a AWAITING_PROOF
       │   → responder: "Recibido ✅, validando..."
       │   → notificar a Johana (push con la imagen)
       │
       ├─ DUDOSO (ej. imagen que no es comprobante)
       │   → responder: "¿Esta es la imagen del pago?
       │      Mándame el comprobante de la transferencia 📸"
       │   → NO cambiar estado
       │
       └─ NO (es otra cosa)
           → flujo normal del bot
              (clasificar como nuevo intent)
```

#### Paso 7: Johana valida (Modo A/C)

Johana revisa en su panel:
- Ve la imagen del comprobante
- Confirma con su app bancaria que llegó el dinero
- Marca en el panel: `✓ Pago confirmado`

#### Paso 8: Bot envía confirmación final (Modo A/C)

```
  Bot: "✅ *¡Pago confirmado!*

        Tu reserva:
        📅 14 de junio
        🏕️ Glamping Montaña + Parapente
        👥 2 personas
        💰 $200.000

        Te esperamos a las 3:00 PM en el punto de encuentro
        [Google Maps link]. ¡Cualquier cosa me escribes! 🌿"
```

### Calendario / disponibilidad

En **Modo A y C**, el bot necesita acceso a un calendario.
Tres fuentes posibles con interface única:

```
  AvailabilityProvider (interface)
  ─────────────────────────────────
  async def is_available(date, duration) -> bool
  async def get_available_slots(month, duration) -> list[Date]
  async def reserve_slot(date, metadata) -> ReservationRef
  async def release_slot(ref)
  async def sync()
```

Adapters:

| Fuente                | Casos de uso                              |
|-----------------------|-------------------------------------------|
| **Local table**       | Tenants simples, sin Google Calendar      |
| **Google Calendar**   | El más común (recomendado)                |
| **iCal URL**          | Cualquier sistema que publique iCal       |
| **MCP server externo**| Sistemas custom (reservas en SaaS externo)|

En **Modo B**, no se usa. El humano consulta su propio
calendario.

### Tabla `reservations` (versión final)

```sql
reservations
┌──────────────────────────────────────────────────┐
│ id, tenant_id                                    │
│ conversation_id (FK)                             │
│ operation_mode_snapshot (autonomous/assisted/    │
│                          hybrid)                 │
│ customer_name, customer_id_number, customer_phone│
│ service_type, reserved_date, reserved_slot_id,   │
│ num_people, combo, total_amount, currency        │
│ status (tentative/pending_payment/confirmed/     │
│         cancelled_by_user/cancelled_auto/        │
│         cancelled_by_human)                      │
│ pre_reserved_by (bot/human), pre_reserved_at     │
│ payment_proof_message_id (FK, nullable)          │
│ payment_confirmed_by_human (FK, nullable)        │
│ payment_confirmed_at                             │
│ handoff_at, cancelled_at, cancel_reason         │
│ notes (jsonb), created_at, updated_at            │
└──────────────────────────────────────────────────┘
```

### Recordatorio automático (Modo A/C)

Si después de 24h el cliente NO ha enviado comprobante:
- Job ARQ envía recordatorio por el bot:

```
  Bot: "Hola {nombre} 👋, ¿pudiste hacer la transferencia?
       Si necesitas los datos de nuevo, dime.
       Si ya pagaste, mándame el comprobante por acá 📸.
       Pasadas 48h sin pago, la reserva se libera."
```

Si después de 48h sigue sin comprobante:
- Job libera la reserva (`reservations.status = cancelled_auto`)
- Notifica a Johana
- El bot puede enviar un último mensaje de cierre

### Cierre elegante (cualquier modo)

Cuando el bot detecta que el cliente solo preguntó pero no
compra, cierra sin insistir. Esto aplica en los 3 modos:

```
  Disparadores de cierre elegante:
  - "solo preguntaba"
  - "ah ok, gracias"
  - "luego miro"
  - silencio > X minutos tras info
  - cambiar tema
  - despedida explícita
  - (Modo A) cliente no confirma tras "hay disponibilidad"

  Bot: "¡Perfecto! Cuando quieras volver,
        aquí estaré 🌿"

  (NO insiste, NO manda publicidad, NO
   hace seguimiento agresivo)
```

### UI del panel: vista de reserva

```
  ┌────────────────────────────────────────────────────┐
  │  RESERVA #2026-00123                                │
  │  ──────────────────────────────────────────        │
  │  Cliente: Juan Pérez                                │
  │  CC: 1234567890                                     │
  │  Fecha: 14 jun 2026                                 │
  │  Combo: 5 (Glamping Montaña + Parapente)            │
  │  Personas: 2                                        │
  │  Total: $200.000 COP                                │
  │  Modo: A (autónomo)                                 │
  │                                                     │
  │  Estado: ✅ CONFIRMED                               │
  │  Pre-reservado por: bot (14 jun 10:23)              │
  │  Pago verificado por: Johana (14 jun 14:32)         │
  │                                                     │
  │  [ 📋 Ver conversación completa ]                   │
  │  [ 📧 Enviar recordatorio check-in ]                 │
  │  [ ❌ Cancelar reserva ]                             │
  └────────────────────────────────────────────────────┘
```

### Métricas por modo

- **Conversion rate por modo**:
  - Modo A: de "cliente confirma" a CONFIRMED
  - Modo B: de H01 a CONFIRMED
  - Modo C: desglosado por intent (con/sin requires_human)
- **Tiempo promedio de cierre** (de intención a pago confirmado)
- **Tasa de abandono**: de READY_FOR_PAYMENT a CANCELLED_AUTO
- **Comprobantes rechazados**: por monto incorrecto
- **% de clientes que solo preguntan y no compran**
  (métrica importante para evaluar cierre elegante)
- **Disponibilidad checks por día** (presión sobre calendario)

---

## 18. Decisiones pendientes y riesgos

### Decisiones de prioridad (a resolver en design review)

| # | Decisión                                          | Recomendación          |
|---|---------------------------------------------------|------------------------|
| 1 | ¿Sprint 3 incluye Wa no oficial?                 | Sí, pero opcional      |
| 2 | ¿MCP server en MVP (Sprint 1) o Sprint 4?        | Sprint 4               |
| 3 | ¿Simulador: solo dev o también cliente?          | Solo dev en MVP        |
| 4 | ¿Emulador es feature obligatoria o nice-to-have? | Nice-to-have en Sprint 3 |

### Riesgos identificados

| Riesgo                                       | Probabilidad | Mitigación                          |
|----------------------------------------------|--------------|-------------------------------------|
| Ban de WhatsApp no oficial                  | Media        | Tener oficial como fallback         |
| LLM no multimodal con plan free             | Alta         | Fallback Whisper configurado        |
| Costo de TTS se dispara                     | Media        | Cache + promoción a predeterminado  |
| Cliente pide cambios en KB muy seguido      | Alta         | Workflow de aprobación + versioning  |
| Migración de tenant a otro server           | Media        | pg_dump documentado + script        |
| Latencia LLM con volumen alto               | Media        | Cache de clasificaciones + rate limit|
| Pérdida de sesión Wa no oficial             | Alta         | Reconexión automática + alerta      |
| Datos sensibles (cédulas) en BD              | Alta         | Hash después de 30d + cifrado reposo|

### Out of scope (para este diseño)

- Multi-idioma (i18n) — solo español por ahora
- A/B testing de respuestas — feature V3+
- Análisis de sentimiento — feature V3+
- Dashboard para múltiples humanos — feature V3+
- Persistencia de carritos — feature V3+
- IVR / llamadas VoIP — feature V3+
- Onboarding self-service del cliente — feature V3+

---

## Anexo A: Referencias al dataset Green Glamping

Para preservar conocimiento durante la migración:

- `01_knowledge_base.json` → se convierte en seed de Green Glamping
- `02_intents.json` → versión original de intents (referencia)
- `03_handoff_triggers.json` → reglas H01-H07
- `04_system_prompt.txt` → system prompt inicial
- `05_horarios.txt` → metadata del tenant
- `06_dataset_completo.jsonl` → datos de entrenamiento (V2)
- `07_dataset_expandido.jsonl` → datos expandidos (V2)
- `08_hallazgos_chats_reales.md` → insights para mejorar KB
- `09_imagenes/` → `data/media/sent/portfolio/`
- `10_audios_scripts/` → `data/media/sent/pregenerated/`
- `01b-01f` (bienvenidas) → `data/seeds/welcome_variants/`

## Anexo B: Glosario

- **Handoff**: transferencia de conversación bot → humano
- **Intent**: clasificación del mensaje del cliente
- **KB**: knowledge base (base de conocimiento del bot)
- **TTS**: text-to-speech
- **STT**: speech-to-text
- **MCP**: Model Context Protocol
- **Tenant**: cliente de la plataforma (cada uno aislado)
- **Schema-separated**: cada tenant tiene su schema en Postgres
- **Baileys**: librería Node.js para WhatsApp no oficial
- **Wizard**: flujo de pasos lineales para configurar
- **Sandbox**: entorno de pruebas aislado del real
- **Decisor**: simulador que recorre el árbol de decisión
