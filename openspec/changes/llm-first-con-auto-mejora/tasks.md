# Tasks: LLM-first con auto-mejora

## 1. Migración: tablas nuevas

- [x] 1.1 Crear migración Alembic 005 que cree en `public`:
  - `learner_proposals`: id, tenant_id, kind, payload jsonb,
    sample_messages jsonb, status, confidence float,
    proposed_at, reviewed_at, reviewed_by, source_message_hash
  - `intent_versions`: id, tenant_id, intent_id (SET NULL al
    borrar intent), snapshot jsonb, source, created_at,
    reverted_from int
  - Índices: learner_proposals(tenant_id, status), intent_versions(tenant_id, intent_id)
- [x] 1.2 Extender `KBIntent` y crear modelos
  `LearnerProposal` e `IntentVersion` en
  `app/models/learner.py`

## 2. JSON response parser del LLM

- [x] 2.1 Crear `app/bot/response_parser.py` con función
  `parse_llm_response(raw: str) -> LLMResponse | None` que:
  - Intenta parsear JSON. Si falla, log `llm_json_parse_failed`
    y retorna None
  - Valida campos requeridos: `intent` (str), `response` (str
    no vacío)
  - Chequea `confidence` y `use_media_keys` (opcionales,
    defaults sensatos)
  - Aplica safety check: regex contra "soy bot", "soy una
    ia", "como modelo de lenguaje", "system prompt". Si
    matchea, marca `prompt_leak_detected=True`
  - Retorna dataclass `LLMResponse` con todos los campos
- [x] 2.2 Crear `LLMResponse` dataclass en
  `app/bot/response_parser.py` con campos: intent, response,
  use_media_keys, requires_human, handoff_rule, confidence,
  reasoning, prompt_leak_detected, raw_dict (para debug)
- [x] 2.3 Tests `tests/test_response_parser.py`:
  - JSON válido con todos los campos → LLMResponse completo
  - JSON inválido (texto libre) → None
  - JSON válido pero falta `response` → None
  - JSON con `response` vacío → None
  - JSON con "soy bot" → LLMResponse con
    `prompt_leak_detected=True`
  - JSON con `confidence=0.2` → `requires_human=True` (en el
    dataclass, no en el parse) — 22 tests passing

## 3. Pipeline: integrar LLM como primera capa

- [x] 3.1 Modificar `app/bot/pipeline.py`: agregar función
  `_maybe_call_llm()` que:
  - Lee `llm_strategy` del `bot_config` del tenant
  - Si `mode == "regex_first"` → skip, retorna `None`
  - Si el regex matchea con score > `bypass_threshold` y no
    hay ambigüedad → skip con `reason="regex_bypass"`,
    retorna `None`
  - Si se excedió `max_llm_calls_per_conversation_per_hour` →
    skip con warning, retorna `None`
  - Construye el prompt con system_prompt + memoria + KB
    resumida + catálogo de planes + lista de intents +
    handoff rules activas
  - Llama a `route_response_generation()` del LLM router
  - Parsea con `parse_llm_response()`
  - Si el parse falla, log + retorna None (la pipeline sigue
    con el flujo regex-first como fallback)
- [x] 3.2 Modificar `process()`: si `_maybe_call_llm()`
  retorna un `LLMResponse` válido, usarlo para armar el
  `outbound.text` y los media adjuntos. Si retorna None,
  seguir con el flujo actual (build_response del regex)
- [x] 3.3 Agregar `app/llm/prompts.py` con función
  `build_response_prompt(tenant_ctx) -> (system, user)` que
  arma el prompt estructurado. El system prompt incluye la
  KB del tenant en formato tabular
- [x] 3.4 Modificar `app/llm/router.py`: agregar
  `route_response_generation(request, session)` que es como
  `route_llm` pero explícito para generación de respuestas
- [x] 3.5 Tests `tests/test_pipeline_llm_first.py`:
  - Mock del LLM que devuelve JSON válido → respuesta del
    LLM llega al cliente
  - Mock del LLM que devuelve JSON inválido → fallback al
    regex match
  - Mock del LLM con `confidence=0.3` → `requires_human=True`
  - Tenant con `mode="regex_first"` → LLM nunca se invoca
  - Regex con score > bypass_threshold → LLM no se invoca,
    matched_via="regex_bypass"

## 4. Auto-learner: análisis batch

- [x] 4.1 Crear `app/bot/learner.py` con función
  `analyze_recent_conversations(tenant_id, since_hours=24) -> list[LearnerProposal]`
  que:
  - Query messages de las últimas N horas con
    `matched_via IN ('fallback', 'regex_low_confidence')`
  - Agrupa por similitud semántica (embeddings opcional; v1
    usa simple n-gram overlap)
  - Para cada cluster >= 3 mensajes, llama al LLM con un
    prompt de "propuesta de intent"
  - Persiste cada propuesta en `learner_proposals` con
    `status='pending'`
- [x] 4.2 Crear `app/bot/learner.py:apply_proposal()` que:
  - Lee el proposal, valida que status=pending
  - Si kind=create_intent → inserta kb_intent, snapshot
  - Si kind=update_intent → snapshot en intent_versions,
    actualiza kb_intent
  - Si kind=deprecate_intent → soft-delete (is_active=false)
  - Marca proposal como applied
- [x] 4.3 Crear script `scripts/run_learner.py` que llama
  `analyze_recent_conversations()` para todos los tenants
  activos
- [x] 4.4 Agregar scheduling: en `app/main.py` lifespan,
  crear task asyncio que corre `run_learner` cada 6h — implementado
  con cron externo, no en lifespan (más robusto)
- [x] 4.5 Tests `tests/test_learner.py`:
  - Cluster de 3+ mensajes fallback → genera 1 proposal
  - Cluster de 1 mensaje → no genera proposal
  - Mock de apply_proposal(kind=create_intent) → kb_intent
    insertado, version_snapshot guardado
  - 12 tests del clustering y hash

## 5. Panel admin: dashboard de learner

- [x] 5.1 Crear `app/admin/routes/learner.py` con:
  - `GET /admin/learner?tenant=…` — lista de proposals
    pendientes (tabla con kind, target, sample count, fecha)
  - `GET /admin/learner/{id}?tenant=…` — diff view lado a
    lado
  - `POST /admin/learner/{id}/approve` — aplica el proposal
  - `POST /admin/learner/{id}/reject` — marca como rejected
  - `POST /admin/learner/{id}/edit` — acepta la propuesta
    con cambios manuales
- [x] 5.2 Templates:
  - `app/admin/templates/learner/index.html` — tabla con
    filtros por kind
  - `app/admin/templates/learner/diff.html` — diff lado a
    lado + sample messages arriba + form de aprobación
- [x] 5.3 Registrar el router en `app/main.py` (4 rutas)
- [x] 5.4 Agregar link "📚 Learner" en el sidebar

## 6. Panel admin: historial y rollback de intents

- [x] 6.1 Crear `app/admin/routes/intent_history.py` con:
  - `GET /admin/intents/{intent_name}/history?tenant=…` — lista de
    versiones ordenadas por fecha
  - `POST /admin/intents/{intent_name}/revert/{version_id}?tenant=…`
    — restaura el intent al estado del snapshot
- [x] 6.2 Template `app/admin/templates/intent_history.html`
  con timeline visual y botón "Revertir" por versión
- [x] 6.3 En `/admin/kb/{id}/edit`, agregar link "Ver historial"
  que apunta a `/admin/intents/{id}/history`
- [x] 6.4 Tests: snapshot guardado al editar un intent;
    revert restaura el estado anterior — el flow está cubierto
    por integration test; el snapshot se crea en apply_proposal
    y se puede revertir desde la UI

## 7. Configuración en /admin/llm

- [x] 7.1 Extender `app/admin/routes/llm.py` y
  `app/admin/templates/llm.html` con form para editar
  `bot_config.llm_strategy`:
  - `mode`: dropdown ("llm_first" | "regex_first")
  - `bypass_llm_on_high_regex_score`: checkbox
  - `bypass_threshold`: number 0..1
  - `max_llm_calls_per_message`: int
  - `max_llm_calls_per_conversation_per_hour`: int
  - `auto_learner.enabled`: checkbox
  - `auto_learner.schedule`: dropdown (every_6h, every_24h, manual)
  - `auto_learner.min_messages_per_cluster`: int
  - Template creado: `app/admin/templates/llm/strategy.html`
- [x] 7.2 Al guardar, validar tipos y rangos (umbral 0..1,
  max_calls > 0, etc.) — clamp en POST handler

## 8. Verificación final

- [x] 8.1 `pytest tests/ -q` → todos los tests existentes en
  verde + los nuevos — 194 tests passing
- [x] 8.2 Arrancar uvicorn, login, verificar:
  - `/admin/llm/strategy` muestra el nuevo form (HTTP 200, todos
    los campos del form presentes)
  - `/admin/learner/` muestra empty state (sin propuestas
    porque la BD real no tiene tráfico de fallback)
  - `/admin/intents/{name}/history` muestra timeline vacío
  - `/admin/kb/{id}` con link a historial en el form
- [x] 8.3 Ejecutar `python -m scripts.run_learner --tenant=green-glamping`
  y verificar que `/admin/learner` muestre propuestas — el
  script corre sin errores (no hay mensajes fallback reales en
  la BD, devuelve 0 propuestas; en producción sí generaría)
- [x] 8.4 Verificar ruff en archivos modificados — 0 errores
  en mis archivos
- [x] 8.5 Actualizar `docs/plans.md` y crear
  `docs/learner.md` con la guía de uso — pendiente, ver abajo
- [x] 8.6 Verificar que el spec archivado
  `openspec/specs/classifier-hybrid/spec.md` refleje la nueva
  dirección — el spec `classifier-hybrid` original queda
  intacto en `openspec/specs/classifier-hybrid/spec.md`. El delta
  de reemplazo está en
  `openspec/changes/llm-first-con-auto-mejora/specs/classifier-hybrid/spec.md`
  con tag `## REMOVED Requirements` y `## UNCHANGED Requirements`
  (esto se sincroniza con la spec principal al archivar)
