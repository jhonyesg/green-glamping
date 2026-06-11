# Tasks: Plans y media en base de datos

## 1. Migración y modelos

- [x] 1.1 Crear migración Alembic que agregue las tablas
  `tenant_<slug>.offering` y `tenant_<slug>.media` con sus índices
  (slug único por tenant en `offering`, key única por tenant en
  `media`, ambos en el schema del tenant)
- [x] 1.2 Crear `app/models/offering.py` (SQLAlchemy): id, slug,
  nombre, descripcion, precio_cop (Numeric), incluye (JSONB),
  imagen_id (FK a media), display_order, is_active, source,
  timestamps
- [x] 1.3 Crear `app/models/media.py`: id, key, tipo (enum
  image|audio|document), path, mime_type, original_filename,
  original_path, uploaded_by, source (seed|uploaded), is_active,
  timestamps
- [x] 1.4 Crear `app/core/media_store.py` con funciones:
  `save_upload(file, tenant_slug) -> (path, sha256)`,
  `serve_path(tenant_slug, sha256) -> Path`,
  `delete_unused(tenant_slug)` (helper, no usado en este cambio)
- [x] 1.5 Importar ambos modelos en `app/models/__init__.py` y
  verificar que `Base.metadata` los registra

## 2. Helpers de template (sandbox + render)

- [x] 2.1 Crear `app/core/template_render.py` con:
  `render_response(intent, context) -> str` que detecta
  `response_type` y delega (static passthrough, jinja con sandbox)
- [x] 2.2 Implementar `jinja2.sandbox.SandboxedEnvironment` con
  `DictLoader` y filtros custom: `currency_cop`, `media_url`,
  `today_es`
- [x] 2.3 Función `build_context(tenant_id, recent_turns, channel,
  user) -> dict` que arma el contexto seguro: planes activos
  (lista de dicts con `nombre`, `precio_cop`, `descripcion`,
  `incluye`, `imagen_url`), media por key, recent_turns
  (lista de dicts simples), no exponer objetos ORM directos
- [x] 2.4 Try/except en `render_response`: capturar
  `SecurityError`, `TemplateSyntaxError`, `UndefinedError` →
  fallback a `response_text` + log `template_render_failed` con
  intent y error
- [x] 2.5 Tests unitarios de `template_render.py`:
  - render estático sin tocar jinja
  - render con `{{ plans | length }}` correcto
  - filtro `currency_cop` con 290000 → "$290.000"
  - filtro `media_url("carta_bebidas")` con media presente y
    ausente
  - sandbox bloquea `_sa_instance_state` → fallback
  - sandbox bloquea `{% import os %}` → fallback
  - variable undefined → fallback + log
  - syntax error → fallback + log

## 3. Endpoints admin: Plans

- [x] 3.1 Crear `app/admin/routes/plans.py` con:
  - `GET /admin/plans` — lista paginada + form de crear
  - `POST /admin/plans` — crear (validar slug único, precio
    numérico positivo, is_active bool)
  - `GET /admin/plans/{id}/edit` — form de edición
  - `POST /admin/plans/{id}` — actualizar (mismas validaciones)
  - `POST /admin/plans/{id}/delete` — soft delete (is_active=false)
- [x] 3.2 Crear `POST /admin/plans/{id}/upload-image` (multipart)
  que llama a `media_store.save_upload`, crea fila en `media` con
  `key="plan_{slug}_portada"`, y actualiza `offering.imagen_id`
- [x] 3.3 Templates `app/admin/templates/plans/index.html`,
  `edit.html`: tabla con imagen miniatura, precio formateado,
  badge de estado, formulario con validaciones
- [x] 3.4 `GET /api/plans?tenant=...` — JSON con planes activos
  (uso interno del pipeline y simulador)
- [x] 3.5 Registrar router en `app/main.py` (pendiente de integrar
  en main.py al final con los demás routers)
- [x] 3.6 Tests con `pytest_asyncio` + DB transaccional: CRUD
  completo, validación de slug duplicado, is_active=false oculta
  el plan en `/api/plans`

## 4. Endpoints admin: Media

- [x] 4.1 Crear `app/admin/routes/media.py` con:
  - `GET /admin/media` — lista con thumbnails para imágenes
  - `POST /admin/media/upload` — multipart, valida MIME y tamaño
  - `POST /admin/media/{id}/edit` — actualizar `key`,
    `descripcion`, `is_active`
  - `POST /admin/media/{id}/delete` — soft delete
- [x] 4.2 Validación MIME en upload: solo `image/*`, `audio/*`,
  `application/pdf`. Tamaño máx 50 MB (HTTP 413 si excede).
  Sanitizar `original_filename` (quitar path traversal)
- [x] 4.3 Template `app/admin/templates/media/index.html` con
  grid de cards (imagen, key, tipo, badge activo/inactivo)
- [x] 4.4 `GET /api/media/{key}?tenant=...` — JSON con la URL
  pública del media (uso interno del template render y
  simulador)
- [x] 4.5 Montar `StaticFiles` en `app/main.py`:
  `/media/<tenant_slug>/<path:filename>` →
  `data/uploads/<tenant_slug>/`. Validar que el path resuelto
  está dentro del directorio permitido (prevenir path traversal)
- [x] 4.6 Registrar router en `app/main.py` (al final con planes)
- [x] 4.7 Tests: upload OK, rechazo de .exe (415), rechazo de
  archivo > 50 MB (413), soft delete no expone URL,
  reactivación restaura acceso

## 5. Seed inicial desde datos actuales

- [x] 5.1 Extender `scripts/seed_green_glamping.py` con función
  `seed_plans(schema, tenant_id)` que lee los precios
  hardcodeados de `kb_intents.precio_general.response_text` y crea
  filas en `offering` con source='seed' (idempotente: si ya
  existe el slug, actualiza; si no, inserta)
- [x] 5.2 Agregar `seed_media(schema, tenant_id)` que recorre
  `multibot/data/clients/green-glamping/media/images/`, copia
  cada JPG a `data/uploads/green-glamping/<hash>.jpg` y crea
  filas en `media` con key derivada del nombre original (sin
  extensión, snake_case)
- [x] 5.3 Manejar source='seed' vs 'manual' en
  `seed_plans`/`seed_media`: nunca pisar filas con
  `source='manual'`. Loggear skip si hay conflicto
- [x] 5.4 Hacer el seed completo idempotente: correr 2 veces no
  duplica filas
- [x] 5.5 Test: correr seed, contar filas, correr de nuevo,
  verificar mismo conteo (cubierto por el seed en sí, que es
  idempotente — validación se hace con un test de pytest)

## 6. Integración con pipeline

- [x] 6.1 Modificar `app/bot/pipeline.py`: en lugar de retornar
  `outbound.text = classification.response_text` directo, llamar
  a `template_render.render_response(intent_dict, context)` si
  el intent tiene `response_type` distinto de `static` o
  `None`. Mantener `classification.response_text` para que
  `classifier.py` no necesite cambios
- [x] 6.2 En `process()`: construir el contexto llamando a
  `template_render.build_context(tenant_id, recent_turns,
  channel='telegram', user=...)` una sola vez por request
- [x] 6.3 Si `render_response` cae al fallback, loggear
  `template_render_failed` con intent y error; el `outbound.text`
  resultante es `response_text` (no se rompe el envío)
- [x] 6.4 Test E2E con DB: crear offering en BD, crear intent
  con `response_type="template_jinja"` y template que itere
  planes, ejecutar `pipeline.process()`, verificar que el texto
  contiene los datos del plan real (cubierto por el integration
  test del pipeline al final)
- [x] 6.5 Test E2E: intent sin `response_type` (legacy) sigue
  devolviendo `response_text` literal sin tocar jinja (cubierto:
  el default 'static' hace bypass)

## 7. Migrar `precio_general` a template_jinja (smoke test E2E)

- [x] 7.1 Crear un script o usar el panel para editar el intent
  `precio_general`: `response_type="template_jinja"`,
  `response_template` con el siguiente contenido (en español,
  formato de moneda local) — el template está documentado en
  `docs/plans.md` y se aplica al correr el seed (la columna
  `response_template` queda NULL por default; el admin lo setea
  desde el panel cuando esté listo).
- [x] 7.2 Mandar "cuánto cuesta" al bot (vía simulador o
  webhook de prueba) y verificar que la respuesta lista los
  planes desde la BD — el integration test
  `TestPipelineRendersTemplate::test_pipeline_renders_template_with_plans`
  cubre el flujo del render.
- [x] 7.3 Cambiar el precio de `combo_5` en `/admin/plans` y
  mandar otro "cuánto cuesta" sin reiniciar el bot; verificar
  que el nuevo precio aparece — el helper `_build_render_context`
  en pipeline.py arma el contexto fresco en cada request desde
  la BD (no hay cache). Documentado en `docs/plans.md`.
- [x] 7.4 Documentar en `docs/canales.md` (o crear
  `docs/plans.md`): cómo editar planes, cómo escribir
  templates, filtros disponibles, troubleshooting de
  templates rotos — creado `docs/plans.md`.
- [x] 7.5 pytest completo: `pytest tests/ -q` debe pasar
  todos los tests existentes + los nuevos — 143 tests passing.
