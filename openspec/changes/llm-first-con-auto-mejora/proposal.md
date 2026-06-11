# Proposal: LLM-first con auto-mejora

## Why

El bot actual funciona con clasificador **regex primero, LLM como fallback**.
Esto produce 3 problemas visibles en producción con Green Glamping:

1. **El bot repite saludos.** El regex matchea "saludo_puro" antes que
   cualquier otro intent, así que "hola" dos veces en una hora
   produce la misma respuesta de bienvenida completa cada vez.
2. **Responde al saludo, ignora el contenido real.** Un cliente
   que escribe "Hola, quiero más información del combo 5" recibe
   la bienvenida en vez de info del combo.
3. **El bot no se auto-mejora.** Si un patrón nuevo aparece
   (ej: "tienen wifi?"), queda en fallback forever. No hay
   manera de detectar y crear intents automáticamente.

El dueño del negocio decide: **dar vuelta la arquitectura** —
el LLM es la primera capa, la KB es material de referencia, y
la IA analiza sus propias conversaciones para mejorar la KB con
supervisión humana. Esto convierte al bot de un sistema estático
basado en reglas a un sistema **vivo que aprende del uso real**.

## What Changes

### Arquitectura nueva

```
MENSAJE ENTRANTE
    ↓
┌─────────────────────────────────────────────────────┐
│  1. Capa de contexto                                  │
│     - Anti-injection (regex, 3 capas, sin cambio)     │
│     - Memoria corta (últimos 10 turnos)               │
│     - Detección de "saludo ya enviado"                │
└─────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────┐
│  2. Capa LLM (SIEMPRE INVOCADA)                       │
│     Recibe como contexto:                              │
│     - System prompt del tenant                         │
│     - Mensaje del usuario                              │
│     - Memoria corta (turnos previos)                   │
│     - Catálogo de servicios activo (planes + precios)  │
│     - Lista resumida de intents disponibles (nombres)   │
│     - Handoff rules activas                            │
│                                                      │
│     Devuelve JSON estructurado:                        │
│     {                                                 │
│       "intent": "info_servicios" | "fallback" |       │
│                  "auto_create:combo_5" | ...           │
│       "response": "texto para enviar al cliente"      │
│       "use_media_keys": ["carta_bebidas", ...]         │
│       "requires_human": false                          │
│       "confidence": 0.0..1.0                          │
│       "reasoning": "por qué elegí este intent"        │
│     }                                                 │
└─────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────┐
│  3. Capa de validación (post-LLM, no rompe si falla)  │
│     - Prompt-leak check (regex "soy bot", "soy una IA")│
│     - Intent existe en KB? Si no, usar fallback       │
│     - response_text tiene sentido? Si no, fallback     │
│     - Si confidence < 0.4 → sugerir "quiere humano"  │
└─────────────────────────────────────────────────────┘
    ↓
┌─────────────────────────────────────────────────────┐
│  4. Capa de envío (existente, sin cambios)            │
│     - humanizer (burbujas)                            │
│     - media adjuntos (response_media_ids del intent)   │
│     - persistencia + métricas                         │
└─────────────────────────────────────────────────────┘

ADICIONAL (en paralelo, no bloquea respuestas):
    ↓
┌─────────────────────────────────────────────────────┐
│  5. Capa de auto-mejora (batch cada N horas)          │
│     - Lee últimas 24h de conversaciones                │
│     - LLM agrupa mensajes sin clasificar (fallback)   │
│     - LLM sugiere:                                     │
│       · Crear intent nuevo (con keywords + response)   │
│       · Actualizar intent existente (mejor response)   │
│       · Depurar intent duplicado                      │
│     - Genera "diff" legible para el admin              │
│     - Dashboard /admin/learner: revisar y aprobar      │
└─────────────────────────────────────────────────────┘
```

### Capabilities nuevas

- `llm-first-response` — la pipeline siempre invoca el LLM primero.
- `context-aware-classifier` — el LLM recibe memoria de conversación.
- `auto-learner-proposals` — análisis batch que sugiere cambios a la KB.
- `learner-dashboard` — vista admin donde se revisan y aprueban sugerencias.
- `intent-rollback` — capacidad de revertir cambios auto-aplicados.

### Capabilities modificadas

- `classifier-hybrid` (cambio de dirección): se reemplaza el
  modelo "regex first, LLM fallback" por "LLM first, regex como
  optimización opcional". El spec existente en
  `openspec/specs/classifier-hybrid/spec.md` se reemplaza.

## Impact

### Backend

- `app/bot/pipeline.py` — agregar paso 2 (LLM) entre clasificador
  regex actual y armado de respuesta. El regex actual se conserva
  como atajo: si hay match con score alto (>0.9) y NO hay
  ambigüedad, se puede saltar el LLM (configurable por tenant).
- `app/bot/classifier.py` — se conserva la función `classify()`
  pero cambia su rol: ahora es `prefilter_classify()`, devuelve
  un candidato regex que se pasa como **sugerencia** al LLM.
- `app/llm/router.py` — agregar `route_response_generation()`
  que toma el contexto completo y devuelve JSON estructurado.
- `app/llm/prompts.py` (nuevo) — plantillas de system prompt
  con la KB del tenant inyectada.
- `app/bot/learner.py` (nuevo) — análisis batch + generación
  de propuestas.
- `app/bot/response_parser.py` (nuevo) — parsea JSON del LLM,
  valida campos, hace fallback si algo falla.

### Modelos / BD

- Nueva tabla `public.learner_proposals`:
  - id, tenant_id, kind ('create_intent' | 'update_intent' |
    'deprecate_intent'), payload jsonb, sample_messages jsonb,
    status ('pending' | 'accepted' | 'rejected' | 'applied'),
    proposed_at, reviewed_at, reviewed_by.
- Nueva tabla `public.intent_versions` (para rollback):
  - id, intent_id, snapshot jsonb (estado completo del intent),
    source ('seed' | 'manual' | 'auto_learner'), created_at,
    reverted_from int (id de la versión revertida).
- Migración Alembic 005: crear ambas tablas en `public`.

### Panel admin

- `/admin/learner` (nuevo) — lista de propuestas pendientes con
  preview del diff (intent actual vs sugerido), botones Aprobar /
  Rechazar / Ver historial.
- `/admin/learner/{id}/diff` (nuevo) — vista detallada del diff
  con samples de mensajes y la respuesta sugerida.
- `/admin/intents/{id}/history` (nuevo) — versiones del intent
  con botón "Revertir a esta versión".
- `/admin/llm` (existente) — agregar config:
  - `mode`: "llm_first" (default) | "regex_first" (legacy, opt-in)
  - `bypass_llm_on_high_regex_score`: bool, default true
  - `bypass_threshold`: float, default 0.9

### Templates admin

- `app/admin/templates/learner/index.html` — lista de propuestas.
- `app/admin/templates/learner/diff.html` — diff lado a lado.
- `app/admin/templates/intent_history.html` — timeline de versiones.
- `app/admin/templates/llm.html` (extensión) — agregar el form
  de los nuevos flags.

### Tests

- `tests/test_response_parser.py` — JSON del LLM válido, inválido,
  con campos faltantes, con leak de prompt.
- `tests/test_learner.py` — generación de propuestas a partir de
  mensajes sintéticos.
- `tests/test_pipeline_llm_first.py` — flujo completo con LLM mock.
- Extender `tests/test_humanizer.py` con casos del nuevo modo.

## Out of scope (cambios futuros)

- **Embeddings / RAG selectivo** — por ahora el LLM recibe la
  KB completa del tenant en cada llamada. Si el catálogo crece
  mucho, se evalúa pasar a embeddings.
- **Multi-modal LLM** (visión de imágenes que el cliente envía)
  — queda para `multimodal-pipeline` (spec ya existe).
- **Editor visual de intents estilo n8n** — queda para
  `editor-de-intents` (próximo OpenSpec separado).
- **A/B testing de respuestas generadas vs hardcodeadas** —
  medir cuál convierte mejor.

## Configuración por tenant

Nuevo objeto en `bot_config.llm_strategy`:

```json
{
  "mode": "llm_first",
  "bypass_llm_on_high_regex_score": true,
  "bypass_threshold": 0.9,
  "max_llm_calls_per_message": 1,
  "max_llm_calls_per_conversation_per_hour": 20,
  "auto_learner": {
    "enabled": true,
    "schedule": "every_6_hours",
    "min_messages_per_cluster": 3,
    "auto_apply_threshold": 0.95
  }
}
```

- `mode: "llm_first"` (default) — nuevo modelo.
- `mode: "regex_first"` — legacy, opt-in para tenants que
  no quieran gastar tokens.
- `bypass_llm_on_high_regex_score: true` — si el regex matchea
  con score > 0.9 y no hay ambigüedad, se ahorra el LLM.
- `max_llm_calls_per_message: 1` — 0 = sin LLM, 1 = máximo
  una llamada por mensaje.
- `auto_learner.auto_apply_threshold: 0.95` — si la confianza
  de la propuesta es > 0.95, se puede auto-aplicar (configurable).
  Default 0.95 + "manual" para forzar revisión.

## Costo estimado

Por mensaje (Green Glamping, ~50 mensajes/día):

| Modo | Costo por mensaje | Costo mensual |
|---|---|---|
| `mode: "regex_first"` (legacy) | $0 | $0 |
| `mode: "llm_first"` con bypass 0.9 | $0.003 (1 de 10 mensajes) | $4.50 |
| `mode: "llm_first"` sin bypass | $0.03 | $45 |
| Auto-learner (batch cada 6h) | $0.10 por batch | $12 |

**Default razonable:** llm_first con bypass 0.9 = ~$17/mes para
un negocio pequeño-mediano.

## Migration Plan

**Pre-deploy:** ninguno.

**Deploy:**
1. Merge del código.
2. Correr `alembic upgrade head` (aplica migración 005: tablas
   `learner_proposals` e `intent_versions`).
3. Activar el nuevo pipeline por tenant: en
   `/admin/llm`, seleccionar provider (ya debe estar
   configurado del cambio anterior) y `mode: "llm_first"`.
   Default: off (los tenants existentes siguen con `regex_first`
   hasta que el admin active el nuevo modo explícitamente).
4. Verificar con el simulador: mandar "hola", luego "hola"
   otra vez. La segunda debe ser corta.
5. Esperar 24h, revisar `/admin/learner` para ver las primeras
   propuestas.

**Rollback:** por tenant, en `/admin/llm` cambiar `mode` a
`"regex_first"`. El bot vuelve al comportamiento original
inmediatamente. La KB no se toca.

**Rollback global:** desactivar el flag de feature en el
servidor, la pipeline sigue con el clasificador regex.
