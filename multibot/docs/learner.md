# Auto-Learner — Guía de operación

> Change: `llm-first-con-auto-mejora`. Estado: implementado.
> Change: `simulador-como-produccion-y-refactor-canales`. Estado: implementado.

## Resumen

El auto-learner es un sistema que **analiza conversaciones reales
del bot y propone mejoras a la base de conocimiento**. Vos revisás
las propuestas en `/admin/learner` y con un clic las aprobás o
rechazás. Las aprobadas se aplican automáticamente.

```
CONVERSACIONES REALES (chat con clientes)
    ↓
[Cron cada 6h] agrupa mensajes sin clasificar por similitud
    ↓
[LLM] genera propuestas de intent nuevo / actualización / deprecación
    ↓
[Tabla learner_proposals] se persiste cada propuesta
    ↓
[Admin] revisa en /admin/learner
    ↓ (aprobar)
[Snapshot automático] en intent_versions (rollback disponible)
[Modificación] se aplica el cambio al intent en kb_intents
```

## Cómo funciona

### Modo LLM-first (recomendado)

Cuando el bot está en `mode: "llm_first"`:

1. Llega un mensaje del cliente.
2. El regex classifier matchea intents con palabras clave.
3. **Si el regex matchea con alta confianza** (score >
   `bypass_threshold`, default 0.9): el bot usa la respuesta
   hardcodeada directamente. No gasta tokens.
4. **Si el regex no matchea o es ambiguo**: el LLM se invoca
   con la KB completa como contexto (planes, media, intents,
   handoff rules) + memoria de la conversación. El LLM
   decide qué decir y devuelve un JSON estructurado.
5. **Si la confianza del LLM es < 0.4**: el bot escala a
   humano automáticamente.
6. La respuesta llega al cliente (posiblemente humanizada
   con burbujas si está activado).

### Auto-learner (batch cada 6h)

1. Se ejecuta `python -m scripts.run_learner` (manualmente o
   vía cron externo).
2. Recolecta los mensajes de las últimas 24h que terminaron
   en `fallback` (el bot no supo responder) o con confianza
   baja del LLM.
3. Agrupa los mensajes por similitud n-gram (Jaccard). Para
   v1 no usa embeddings (más simple, sin infraestructura
   adicional).
4. Para cada cluster con >= `min_messages_per_cluster`
   mensajes (default 3), llama al LLM con un prompt de
   "propuesta de intent".
5. Persiste cada propuesta en `public.learner_proposals` con
   `status='pending'`.
6. El admin las ve en `/admin/learner`.

## Activar el modo LLM-first

1. Asegurate de tener un LLM provider configurado en
   `/admin/llm`. Si no, agregá uno (MiniMax, OpenAI, Groq,
   etc.).
2. Andá a `/admin/llm/strategy?tenant=green-glamping`.
3. Cambiá `Modo` de "regex_first (legacy, sin LLM en runtime)"
   a "llm_first (IA genera cada respuesta)".
4. Ajustá:
   - **Bypass threshold**: 0.9 (default). Más alto = más
     restrictivo (ahorra tokens cuando el regex es muy claro).
   - **Max llamadas LLM por mensaje**: 1 (recomendado).
   - **Max llamadas LLM por conversación/hora**: 20.
5. Activá el auto-learner.
6. Click "Guardar configuración".

A partir de ahí, cada mensaje del bot invoca al LLM (salvo
bypass por regex de alta confianza).

## Revisar propuestas del learner

1. Andá a `/admin/learner?tenant=green-glamping`.
2. Cada propuesta tiene:
   - **kind**: `create_intent` (nuevo), `update_intent`
     (mejorar existente), `deprecate_intent` (borrar duplicado).
   - **sample_messages**: los 3-5 mensajes que motivaron la
     propuesta.
   - **confidence**: qué tan seguro está el LLM (0..1).
   - **proposed_at**: cuándo se generó.
3. Click "Ver diff completo" para ver el detalle, incluyendo
   el estado actual del intent (si existe) lado a lado.
4. Tres acciones:
   - **Aprobar**: aplica el cambio (crea snapshot en
     `intent_versions` para rollback).
   - **Rechazar**: marca como rejected. El learner no
     re-propondrá el mismo cluster (memoización por hash).
   - **Editar antes de aprobar**: cambias la respuesta o
     keywords y click "Aprobar y aplicar" con los cambios.

## Rollback de intents

Cada vez que un intent se modifica (manual o auto-learner),
se guarda un snapshot en `public.intent_versions`. Para
revertir:

1. Andá a `/admin/intents/{intent_name}/history?tenant=…`.
2. Cada versión tiene fecha, source (`seed`, `manual`,
   `auto_learner`, `revert`), y un botón "Revertir a esta
   versión".
3. Click "Revertir" — el intent vuelve al estado de esa
   versión. El estado actual se guarda como nueva versión
   (para que puedas deshacer el rollback).

## Costos

| Modo | Costo/mensaje | Costo/mes (50 mensajes/día) |
|---|---|---|
| `regex_first` (legacy) | $0 | $0 |
| `llm_first` con bypass 0.9 | ~$0.003 | ~$5 |
| `llm_first` sin bypass | $0.03 | $45 |
| Auto-learner batch cada 6h | $0.10/batch | $12 |

**Default razonable:** ~$17/mes para un negocio como Green
Glamping (Green Glamping hace ~50 mensajes/día).

## Smoke test

```bash
# 1. Aplicar migraciones
cd multibot
.venv/bin/alembic upgrade head

# 2. Correr el learner manualmente
.venv/bin/python -m scripts.run_learner --tenant=green-glamping
# Output esperado: "✓ learner_done tenant=green-glamping proposals_created=N"

# 3. Ver las propuestas en el panel
# http://localhost:8000/admin/learner/?tenant=green-glamping

# 4. Probar el modo LLM-first
# Activar en /admin/llm/strategy
# Mandar un mensaje en el simulador y verificar que el LLM
# genera la respuesta (matched_via="llm" en la métrica)
```

## El simulador como clon de producción

El simulador (`/admin/simulate/`) ejecuta ahora la misma
`pipeline.process()` que usa el bot real, con la diferencia
que `dry_run=True` impide que escriba en BD.

**Ventajas:**
- Lo que ves en el simulador = lo que recibe el cliente real.
- Trace paso a paso: `resolve_tenant → anti_injection → classify → llm_decision → build_response`.
- El step `llm_decision` muestra si el regex hizo bypass (con score y threshold) o si el LLM se invocó (con intent, confidence, reasoning).
- No se persiste nada en la base de datos (no afecta conversaciones reales).

**Uso:**
1. Andá a `/admin/simulate/`.
2. Elegí el canal (telegram, whatsapp, etc.) desde el dropdown.
3. Mandá un mensaje de prueba.
4. Verificá el trace: si dice `regex_bypass` con score > threshold, el LLM no se invocó (0 costo).
5. Si dice `llm_invoked`, el LLM sí se usó — podés ver las métricas en `/admin/llm/usage`.

**Integración con métricas LLM:**
Cada vez que el LLM se invoca (tanto en producción como en el simulador cuando `dry_run=False` no aplica), se registra en `public.llm_usage`:
- `tenant_id`, `provider_id`, `latency_ms`, `tokens_used`, `cost_usd`.
- Las métricas se ven en `/admin/llm/usage` (últimos 30 días por provider).

## Troubleshooting

| Problema | Causa probable | Solución |
|---|---|---|
| `/admin/learner` da 500 | Migración 005 no aplicada | `alembic upgrade head` |
| El bot no llama al LLM | `mode` sigue en `regex_first` o no hay provider configurado | Ver `/admin/llm` y `/admin/llm/strategy` |
| El LLM devuelve JSON inválido | Prompt mal interpretado | El parser cae al regex match automáticamente |
| El LLM "alucina" precios | Falla del system prompt | Los precios están inyectados como dato duro, no se inventan |
| El learner no genera propuestas | No hay suficientes mensajes fallback | Esperar más tráfico o bajar `min_messages_per_cluster` |
| Quiero re-aplicar una propuesta rechazada | Por diseño, se memeoiza por hash | Crear manualmente desde `/admin/kb/new` |
| Rollback no funciona | El snapshot no se creó | Verificar que `apply_proposal` haya corrido (deja logs) |

## Cambios de comportamiento vs el bot anterior

| Antes | Ahora |
|---|---|
| Bot matchea regex, responde con hardcodeado | Bot matchea regex, pero LLM reescribe la respuesta con la KB como contexto |
| "Hola" siempre matchea el mismo intent "saludo_puro" | El LLM puede distinguir "hola solo" vs "hola + pregunta" |
| Mensajes sin clasificar quedan en fallback forever | Auto-learner los agrupa y propone intents cada 6h |
| Cambios en la KB requieren redeploy | Cambios se reflejan al instante (vía BD) |
| Sin historial de cambios | Cada cambio genera un snapshot, con rollback 1-click |
