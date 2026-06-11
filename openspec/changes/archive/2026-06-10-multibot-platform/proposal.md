# Proposal: Multibot — Plataforma de Atención Multi-Canal

## Why

Green Glamping Chipaque opera hoy un bot de Telegram sobre n8n
que responde preguntas comerciales, gestiona objeciones de precio
y transfiere a un humano cuando hay intención real de reserva. La
KB está consolidada (33 intents, 7 handoffs tipificados, 6
objeciones canned) y la operación funciona, pero la
plataforma subyacente (n8n + workflows cableados) no escala a
múltiples clientes, no soporta otros canales, y limita la
flexibilidad de configuración por tenant.

**Necesidad inmediata**: dar al negocio una plataforma
multi-tenant multi-canal sobre la que pueda crecer la operación
(WhatsApp oficial + no oficial, Telegram, webchat) y que pueda
ofrecer a otros clientes con baja fricción de onboarding.

**Oportunidad estratégica**: el LLM propio (MiniMax, 12B
parámetros, multimodal) ya está disponible vía API. Es el
diferenciador de costo y capacidad. La plataforma debe ser
LLM-agnóstica para que cada tenant pueda usar el suyo (o el de
nosotros) según su plan.

## What Changes

- **Nueva plataforma backend** en Python/FastAPI con arquitectura
  multi-tenant (schema-separated en PostgreSQL) que reemplaza el
  bot actual de n8n para Green Glamping como primer cliente.
- **Sistema multi-canal** con adapters normalizados para
  WhatsApp oficial, WhatsApp no oficial (vía microservicio
  Node+Baileys), Telegram y Webchat. Envío multimedia siempre
  como media nativa, nunca como reenvío.
- **Sistema multi-LLM agnóstico** con interface unificada
  (chat, transcribe, TTS, vision). MiniMax es el primer
  adapter; cualquier provider OpenAI-compat puede agregarse.
- **STT inteligente**: si el LLM del tenant es multimodal, pasa
  audio directo; si no, usa Whisper como fallback configurable.
- **Tres modos de operación** por tenant: autónomo (bot
  gestiona todo, humano solo valida pago), asistido (humano
  gestiona, bot filtra) e híbrido (recomendado, configurable
  por intent). El bot valida disponibilidad (calendario
  propio, Google Calendar, iCal o MCP externo) en modos
  autónomo e híbrido.
- **Panel admin wizard lineal** (FastAPI + Jinja + HTMX) con
  flujo de 6 pasos para onboarding de tenants, edición
  visual de KB, gestión de conversaciones, métricas,
  emulador sandbox y workflow de retroalimentación del
  cliente con aprobación.
- **Sistema TTS** con voz clonada fija por tenant, cache
  automático, promoción de TTS frecuentes a predeterminados,
  y rotación de variantes de voz para evitar monotonía.
- **Handoff inteligente con ventanas configurables** (12h/48h
  /90d) que distingue entre "cliente insiste tras handoff
  reciente" (bot calla) y "cliente vuelve tras 48h" (bot
  retoma).
- **Emulador/decisor visual** tipo PSeInt que recorre el
  árbol de decisión del bot y muestra qué respuesta saldría
  sin enviarla, exportable como test reproducible.
- **Servidor y cliente MCP** para interoperabilidad con
  herramientas externas (Claude Desktop, n8n, CRMs).
- **Ciclo completo de reserva** con estados detallados
  (pre-reserva, espera de pago, comprobante, confirmación,
  cancelaciones), recordatorios automáticos 24h/48h, y
  plantilla de mensaje de pago configurable por tenant.
- **Política de retención multimedia** con quarantine de 7
  días antes de hard delete, configurable por tenant
  (default 90 días).
- **Dev en host** (Postgres existente) → migrable a
  docker-compose para deploy. Cada tenant se puede migrar
  vía `pg_dump` a su propia infraestructura.

## Capabilities

### New Capabilities

- `multi-tenant-foundation`: Aislamiento de tenants
  (schema-separated), modelos base (Tenant, Channel,
  LLMProvider, MediaAsset), contexto de tenant por request,
  migraciones Alembic.
- `channel-adapters`: Interface común de canal, adapters para
  WhatsApp oficial, WhatsApp no oficial, Telegram, Webchat.
  Mensaje universal normalizado. Verificación de webhooks.
  Envío multimedia nativo (no forward).
- `llm-providers`: Interface LLMProvider, router por tenant,
  adapter MiniMax primero, soporte OpenAI-compat. STT
  inteligente (multimodal vs Whisper fallback).
- `classifier-hybrid`: Clasificador regex contra KB, LLM
  fallback para intents no cubiertos, cache de
  clasificaciones, anti-inyección de 3 capas, manejo de
  contextos multimodales.
- `handoff-intelligent`: Sistema de handoff con reglas
  configurables por tenant y por modo, ventanas de pausa
  configurables, notificación al humano, lógica de
  "callar inteligente" según tiempo transcurrido.
- `availability-providers`: Interface unificada de calendario
  con adapters (tabla local, Google Calendar, iCal URL,
  MCP server externo). Cache local de slots. Reserva y
  liberación de slots.
- `reservation-lifecycle`: Ciclo completo de reserva con
  estados (tentative → pending_payment → confirmed →
  cancelaciones), tabla reservations, recordatorios
  automáticos, plantilla de mensaje de pago.
- `tts-system`: TTS con voz clonada, cache de generaciones
  con promoción automática a predeterminados, rotación de
  variantes de voz.
- `admin-panel-wizard`: Panel admin con wizard de 6 pasos
  para onboarding, pantallas de KB/canales/LLM/TTS/handoffs
  /métricas, retroalimentación con workflow de aprobación.
- `emulator-decisor`: Simulador sandbox que recorre el
  árbol de decisión del bot, muestra el camino tomado y
  la respuesta que saldría, exportable como test.
- `mcp-integration`: Servidor MCP que expone tools y
  resources de Multibot, y cliente MCP para consumir
  servidores externos (CRMs, calendars, payments).
- `multimodal-pipeline`: Procesamiento de archivos
  multimedia entrantes (imagen → vision, audio → STT,
  video → extracción de audio + frame), envío multimedia
  saliente como media nativa, manejo de documentos.
- `feedback-workflow`: Sistema de retroalimentación del
  cliente (marcar respuestas, sugerir intents, editar
  respuestas, reporte libre) con workflow de aprobación
  que el admin revisa.
- `media-retention-policy`: Política de retención
  configurable por tenant, sistema de quarantine, job
  nocturno de limpieza, índices de búsqueda de archivos
  huérfanos.

### Modified Capabilities

Ninguna. Este es un proyecto greenfield; no hay capabilities
existentes en `openspec/specs/`.

## Impact

- **Reemplazo del bot actual de n8n** para Green Glamping. La
  KB de 33 intents se migra tal cual al seed del primer
  tenant. Downtime esperado: <1 hora con cutover cuidadoso.
- **PostgreSQL**: se usa el container Postgres existente del
  usuario. Se crean schemas nuevos (uno por tenant) en esa
  misma instancia. No requiere nuevo container de BD para
  MVP.
- **Microservicio nuevo Node.js + Baileys** para WhatsApp no
  oficial. Servicio independiente que se comunica con
  Multibot por HTTP REST. Riesgo de ban (mitigado por tener
  canal oficial como fallback).
- **APIs externas nuevas**:
  - Meta Cloud API (WhatsApp oficial): requiere verificación
    de negocio (semanas) y partner.
  - Google Calendar API: OAuth por tenant, scopes de lectura
    de calendario.
  - LLM provider APIs: MiniMax (nuestra), OpenAI, Anthropic,
    etc. según elección del tenant.
- **Stack de desarrollo**:
  - Backend: Python 3.11+, FastAPI, SQLAlchemy 2.0 async,
    Alembic, Pydantic v2.
  - Panel: FastAPI + Jinja2 + HTMX + CSS custom.
  - BD: PostgreSQL 14+ (existente).
  - Cache/cola: Redis 7+.
  - Workers: ARQ.
  - Container: Docker + docker-compose (Fase 2+).
- **Equipo**: 1 dev fullstack (tú). Plazo MVP: 4-6 semanas
  para Sprint 0 + Sprint 1 + Sprint 2.
- **Riesgos**:
  - Ban de WhatsApp no oficial (mitigado: oficial primero).
  - Latencia LLM con volumen alto (mitigado: 90% de
    mensajes caen en regex sin LLM).
  - Pérdida de sesión Wa no oficial (mitigado: reconexión
    automática + alerta).
  - Costos de TTS (mitigado: cache + promoción).
- **Out of scope** (no-goals explícitos):
  - Multi-idioma sofisticado (solo español por ahora).
  - Constructor visual sin código (el panel es para admins,
    no para clientes finales).
  - A/B testing, análisis de sentimiento, IVR, carritos
    persistentes (features V3+).
