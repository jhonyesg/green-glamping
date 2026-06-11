# Design: LLM-first con auto-mejora

## Context

El bot actual usa `app/bot/pipeline.py` con un clasificador
regex (`app/bot/classifier.py`) como primera capa, regex match
→ `build_response` → humanizer → enviar. LLM solo se invocaba
como fallback en el change archivado `multibot-platform` (nunca
implementado al 100%).

El cambio invierte el orden: **LLM siempre se invoca** con
contexto completo (mensaje + memoria + KB del tenant), y el
regex se mantiene como **pre-filtro barato** para ahorrar
llamadas al LLM cuando hay match muy claro.

La infraestructura LLM ya está armada:
- `app/llm/router.py` con failover entre providers
- `app/llm/minimax.py` y `openai_compat.py` adapters
- `public.llm_providers` con capabilities
- `app/admin/routes/llm.py` con CRUD de providers

Lo que falta es **cambiar el contrato del clasificador** y
**agregar el loop de auto-mejora**.

## Goals / Non-Goals

**Goals:**
- LLM-first como modo por defecto (opt-in por tenant).
- JSON estructurado del LLM con validación robusta.
- Auto-mejora con sugerencias al admin vía dashboard.
- Rollback de intents modificados.
- Costo controlado (bypass con regex de alta confianza).
- Retrocompatible: tenants existentes siguen con regex_first
  si no activan el nuevo modo.

**Non-Goals:**
- Embeddings / RAG selectivo (queda para futuro).
- Multi-modal LLM (spec `multimodal-pipeline` ya existe aparte).
- Editor visual de intents (cambio `editor-de-intents`).
- A/B testing automático de respuestas.

## Decisions

### Decisión 1: El LLM devuelve JSON estructurado, no texto libre

La pipeline actual espera `response_text` (string). El nuevo
contrato es un JSON con campos específicos:

```json
{
  "intent": "info_servicios" | "combo_5_info" | "fallback",
  "response": "Texto para enviar al cliente",
  "use_media_keys": ["carta_bebidas", "spa_pareja"],
  "requires_human": false,
  "handoff_rule": null,
  "confidence": 0.85,
  "reasoning": "Cliente pregunta por combo 5, precio y qué incluye. Tengo el plan en el catálogo."
}
```

**Por qué JSON y no texto libre:**
- Validador puede rechazar respuestas que rompan formato.
- El campo `intent` permite mapear a `kb_intents.id` para
  adjuntar media, handoff rules, métricas.
- El campo `use_media_keys` resuelve directamente a URLs de
  media sin pasar por la KB hardcodeada.
- El campo `confidence` permite escalado a humano cuando
  hay duda.

**Por qué no llamar al LLM solo para "elegir intent" y
después armar respuesta de la KB:**
- Es lo que proponía el change archivado `classifier-hybrid`.
- El admin explícitamente quiere que el LLM **genere la
  respuesta** usando la KB como contexto. Esto es más flexible:
  el LLM puede reformular, agregar contexto, ajustar tono.

### Decisión 2: Bypass del LLM cuando el regex matchea con alta confianza

Por costo y latencia, si el regex matchea con `score > 0.9` y
no hay ambigüedad, se puede usar la respuesta hardcodeada del
intent directamente sin invocar al LLM.

**Configurable por tenant:**
- `bypass_llm_on_high_regex_score: true` (default)
- `bypass_threshold: 0.9` (default)

**Por qué no siempre bypass:**
- El LLM puede haber actualizado la KB con información nueva
  que el regex no conoce (ej: "tenemos nueva promo de
  Halloween" agregado al `response_template` del intent).
- En ese caso, el LLM usa la info nueva y la respuesta es
  más rica que el hardcodeado.
- El admin controla el balance: bypass alto = ahorra
  tokens, bypass bajo = siempre LLM.

**Por qué no siempre LLM:**
- Costo: ~$0.03 por mensaje sin bypass.
- Latencia: ~500ms extra por llamada al LLM.
- Para intents con respuesta estable y bien probada
  (ej: "horarios"), el regex es suficiente.

### Decisión 3: Validación robusta del JSON del LLM

El LLM puede devolver JSON malformado, campos faltantes, o
respuestas que rompen reglas (ej: revelar que es un bot).

Tres capas de validación:

1. **JSON parse** — si falla, fallback a regex match.
2. **Schema check** — campos requeridos presentes. Si falta
   `response` o `intent`, fallback.
3. **Safety check** — regex contra "soy bot", "soy una IA",
   "como modelo de lenguaje". Si matchea, reemplazar respuesta
   con una genérica en personaje + log `prompt_leak`.

**Por qué tres capas:** el LLM es probabilístico. Aunque
funcione 99% del tiempo, los 1% de errores son visibles (cliente
ve respuesta rota o fuera de personaje). El costo de validar
es trivial comparado con el costo reputacional de un error.

### Decisión 4: Auto-mejora = análisis batch + propuestas, NO auto-apply

El LLM analiza conversaciones de las últimas 24h, agrupa
mensajes que matchearon `fallback` por similitud semántica, y
genera propuestas:

```
PROPUESTA 1: Crear intent "wifi_info"
  4 mensajes similares sin clasificar:
  - "Tienen wifi?"
  - "Cómo es el señal?"
  - "Hay internet?"
  - "WiFi funciona?"
  Respuesta sugerida: "Sí, contamos con WiFi. ⚠️ Estamos
    en la punta de la montaña más alta del oriente de
    Cundinamarca, así que cuando hay nube baja la señal
    puede ser inestable. Es parte de la experiencia de
    desconexión y conexión con la naturaleza 🌄"
  Keywords sugeridos: ["wifi", "wi-fi", "se[ñn]al", "internet"]
  
  [Aprobar y crear]  [Rechazar]  [Editar antes de crear]
```

**Por qué batch (cron) y no por-mensaje:**
- Costo: analizar 50 mensajes con LLM en batch cuesta $0.10.
  Por-mensaje costaría 50×$0.03 = $1.50.
- Latencia: las propuestas se revisan en horarios tranquilos.
- Menos ruido: un solo "crear intent wifi_info" en vez de
  4 propuestas de "crear intent para 'tienen wifi'",
  "crear intent para 'cómo es el señal'", etc.

**Por qué no auto-apply con confianza > 0.95:**
- Una propuesta auto-aplicada que está mal cuesta más
  revertir que aprobar manualmente.
- El admin mantiene control de la KB.
- Si el LLM tiene 95% de confianza, lo más probable es
  que esté bien, pero ese 5% importa.
- Mitigación: si el admin está conforme, puede subir el
  threshold a 0.99 y auto-apply algunas categorías.

### Decisión 5: Rollback via versiones de intent

Cada vez que un intent se modifica (manual o auto), se
guarda snapshot en `intent_versions`. El admin puede:

- Ver historial de cambios con diff lado a lado.
- Revertir a cualquier versión anterior.
- Marcar una versión como "buena" (para reference).

**Por qué versionar y no solo `updated_at`:**
- Sin historial, revertir es imposible.
- Si un intent auto-aplicado rompe respuestas, el admin
  necesita un botón "deshacer" de un click.
- El historial también sirve para análisis: "esta respuesta
  mejoró las conversiones un 20% desde que se cambió".

**Costo de almacenamiento:** cada intent son ~2-5 KB
serializado. Con 30 intents y 100 versiones cada uno, son
~15 MB. Trivial.

### Decisión 6: Modo `llm_first` es opt-in, no default

Cuando un tenant tiene el sistema funcionando bien con
`regex_first` (no gasta tokens, respuestas estables), un
cambio de modo brusco podría introducir variabilidad. Por eso:

- **Default en tenants nuevos:** `llm_first` (para que empiecen
  con el sistema más capaz).
- **Default en tenants existentes:** `regex_first` (preserva
  comportamiento conocido).
- **El admin cambia manualmente** en `/admin/llm` cuando
  quiera. El cambio es reversible al instante.

Esto también permite A/B testing: dejar `regex_first` para
un canal (ej: WhatsApp) y `llm_first` para otro (ej: Telegram),
comparar calidad de respuestas.

## Risks / Trade-offs

**[R1] Costo de tokens si se deja activado por error**
→ `max_llm_calls_per_message: 1` y `max_llm_calls_per_conversation_per_hour: 20`
limitan el daño. El admin ve el contador en `/admin/llm`.
El panel avisa cuando el costo del mes supera un umbral.

**[R2] El LLM alucina y da info falsa sobre precios**
→ Las cifras de precios se inyectan como dato duro en el
prompt del LLM (`planes: [{nombre: "Combo 5", precio_cop: 290000}, ...]`).
El LLM no inventa: solo elige qué decir de lo que está en el
contexto. El system prompt incluye la instrucción explícita:
"Si la información no está en el contexto, no la inventes.
Usa la respuesta fallback."

**[R3] Auto-mejora sugiere intents duplicados**
→ El dashboard hace check de similitud con intents existentes
antes de proponer. Si la similitud es > 0.8, en vez de
"crear nuevo" propone "actualizar existente".

**[R4] Latencia del LLM en tiempo real**
→ El LLM agrega ~500ms-1s por mensaje. Para un bot de
Telegram/WhatsApp eso es OK (latencia normal de chat).
Si llega a ser problema, se cachean respuestas por hash del
mensaje + contexto.

**[R5] Versiones de intent crecen sin límite**
→ Se retienen las últimas 50 versiones por intent. Las más
viejas se purgan. Para auditoría, queda el log de cambios
en `learner_proposals`.

**[R6] El spec `classifier-hybrid` existente se contradice con el nuevo**
→ El spec `classifier-hybrid` se reemplaza. El cambio
documenta explícitamente esto en su propuesta. El spec
archivado en `openspec/specs/classifier-hybrid/spec.md` se
actualiza con la nueva dirección (LLM-first, no regex-first).

## Migration Plan

**Pre-deploy:** ninguno. Cambio retrocompatible (opt-in).

**Deploy:**
1. Merge del código.
2. Correr `alembic upgrade head` (aplica migración 005).
3. Sin acción adicional: el bot sigue funcionando con
   `regex_first` para todos los tenants.
4. El admin activa `llm_first` por tenant desde `/admin/llm`
   cuando esté listo. Default sugerido: empezar con
   `bypass_llm_on_high_regex_score=true` y `bypass_threshold=0.95`
   (ahorra tokens cuando el regex es muy claro).
5. Verificar en simulador: mandar "hola" dos veces. La
   segunda debe ser más corta (o diferente) que la primera.
6. Esperar 24-48h, revisar `/admin/learner` para las
   primeras propuestas.

**Rollback por tenant:** en `/admin/llm`, cambiar `mode` a
`"regex_first"`. Cambio instantáneo, sin reinicio.

**Rollback global:** ningún efecto secundario. El feature
flag está en `bot_config` del tenant, no en el código del
servidor. Desactivar todos los tenants cierra el flujo LLM
global.

## Open Questions

1. **¿Cada cuánto corre el auto-learner?** Propuesto: cada 6h
   en background. ¿O diario? ¿O manual?
   → Empezar con 6h. Ajustable.

2. **¿El admin debería poder DESHABILITAR intents auto-creados
   individualmente?** (no solo revertir la versión, sino
   marcar el intent como "no auto-crear más").
   → Sí, agregar campo `auto_create_disabled: bool` en
   `kb_intents`. Si está true, el learner no propone crear
   intents similares.

3. **¿La propuesta de auto-mejora incluye el historial de
   mensajes que la motivaron?** (para que el admin vea
   contexto antes de aprobar)
   → Sí, campo `sample_messages jsonb` con los 3-5 ejemplos.

4. **¿Límite de tamaño de la KB inyectada en el prompt?**
   → Soft limit: si la KB tiene > 4000 tokens, se trunca a
   los intents más usados (medido por `use_count` en
   `intent_metrics`). Hard limit: 8000 tokens del lado de la
   pipeline; si excede, fallback a `regex_first` para ese
   mensaje y log.
