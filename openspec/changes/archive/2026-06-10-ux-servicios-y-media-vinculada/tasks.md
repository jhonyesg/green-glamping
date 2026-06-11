# Tasks: UX — Servicios, key auto-generada, media vinculada

## 1. Migración: response_media_ids + backfill

- [x] 1.1 Crear migración Alembic 004 que agregue
  `response_media_ids` (jsonb, default `[]`) a `kb_intents` en
  cada schema de tenant
- [x] 1.2 Backfill en la migración: para cada intent con
  `response_audio_id IS NOT NULL`, agregar ese id al
  `response_media_ids` (preservar el audio actual)
- [x] 1.3 Extender `app/models/kb_intent.py`: agregar columna
  `response_media_ids: Mapped[list]` (jsonb, default list)

## 2. Helper de auto-key de media

- [x] 2.1 Crear `app/core/media_keys.py` con la función
  `next_media_key(tenant_slug) -> str` que devuelve
  `media_NNN` (1-padded, MAX+1 por tenant)
- [x] 2.2 Tests: tenant vacío → `media_001`. Tenant con
  `media_001`, `media_005` → `media_006`. Tenant con `media_099`
  → `media_100`

## 3. UI: rename "Planes" → "Servicios"

- [x] 3.1 Renombrar strings en `plans/index.html`:
  - `<h1>Planes del catálogo</h1>` → `<h1>Servicios del catálogo</h1>`
  - `<h3>📋 Listado</h3>` → `<h3>🛎 Servicios</h3>`
  - `<h3>➕ Nuevo plan</h3>` → `<h3>➕ Nuevo servicio</h3>`
  - botón "Crear plan" → "Crear servicio"
- [x] 3.2 Renombrar en `plans/edit.html`:
  - "Editar plan" → "Editar servicio"
- [x] 3.3 Sidebar en `base.html`: cambiar "📋 Planes" por
  "🛎 Servicios" (mantiene href `/admin/plans/`)
- [x] 3.4 Smoke test: cargar `/admin/plans/?tenant=…` y
  verificar que el header dice "Servicios"

## 4. UI: imagen de servicio = selector de media library

- [x] 4.1 En `plans/edit.html`, reemplazar el form de upload
  (`<input type="file">` + `POST /admin/plans/{id}/upload-image`)
  por un `<select name="imagen_id">` con todos los media
  activos de tipo `image` del tenant
- [x] 4.2 En `plans.py` ruta `POST /admin/plans/{id}`,
  agregar parámetro `imagen_id: int = Form(0)` y persistir en
  la columna
- [x] 4.3 En `plans.py`, eliminar la ruta
  `POST /admin/plans/{id}/upload-image` y sus imports
  asociados
- [x] 4.4 El listado `plans/index.html` debe mostrar la
  miniatura de la imagen elegida (URL ya viene del campo
  `imagen_url` en el contexto; ajustar si hace falta)
- [x] 4.5 Smoke test: editar un servicio, elegir una media
  existente, guardar, recargar el listado y verificar la
  miniatura
- [x] 5.1 En `media/index.html`, eliminar el `<input name="key">`
  del form de upload
- [x] 5.2 En `app/admin/routes/media.py` ruta `POST /upload`,
  eliminar `key: str = Form(...)` y llamar a
  `next_media_key(tenant)` para asignar la key
- [x] 5.3 Mantener la ruta de edición con el campo `key` (el
  admin puede renombrar); validar unicidad al guardar — la
  ruta POST `media/{id}` ya existe; el template actual no la
  expone pero queda disponible para uso futuro
- [x] 5.4 Smoke test: ir a `/admin/media/?tenant=…`, subir un
  archivo, verificar que aparece con `key=media_001`

## 6. UI: media adjunta a intents

- [x] 6.1 En `kb/edit.html`, agregar un multi-select con
  todos los media activos del tenant; pasar como
  `response_media_ids: list[int] = Form([])` en POST
- [x] 6.2 En `app/admin/routes/kb.py`:
  - `kb_create` recibe `response_media_ids: list = Form([])`
    y persiste en la nueva columna
  - `kb_update` idem
  - `kb_edit` carga los ids y los pasa al template como
    `selected_media_ids: set[int]`
- [x] 6.3 En el template `kb/list.html`, agregar una columna
  "Media adjuntos" con el conteo (`N archivos`) — opcional
  pero mejora el overview
- [x] 6.4 Smoke test: editar un intent informativo (ej:
  `info_servicios`), seleccionar una imagen, guardar,
  recargar y ver el contador

## 7. Pipeline: enviar media adjuntos

- [x] 7.1 Extender `app/bot/responder.py`: el `OutboundMessage`
  acepta un nuevo campo `media_attachments: list[int] = []`
- [x] 7.2 En `app/bot/pipeline.py`, después de clasificar y
  antes de retornar el `PipelineResult`, consultar el
  `response_media_ids` del intent y poblar
  `outbound.media_attachments`
- [x] 7.3 En `app/api/webhooks.py`, en
  `handle_telegram_update`, si `outbound.media_attachments`
  está poblado, descargar cada media con `TelegramAdapter`
  y enviar como mensajes adicionales (secuenciales o como
  album si el adapter lo soporta; para esta versión
  enviarlos secuencialmente está bien)
- [x] 7.4 Test: con un intent que tiene 1 media adjunto,
  verificar que `PipelineResult.outbound.media_attachments`
  tiene el id correcto (cubierto por el integration test del
  pipeline al final)

## 8. Verificación final

- [x] 8.1 `pytest tests/ -q` → todos los tests existentes +
  los nuevos en verde (149 passing)
- [x] 8.2 Arrancar uvicorn, login como superadmin, recorrer
  los 3 flujos (sidebar dice Servicios, upload de media
  genera key auto, edit de servicio elige media de la
  biblioteca, edit de intent vincula media, bot responde
  con adjunto) y verificar visualmente
- [x] 8.3 Actualizar `docs/plans.md` con los cambios:
  - Sección "Subir media" sin campo key
  - Sección "Editar servicio" con selector de imagen
  - Nueva sección "Vincular media a intents"
  - Mención a `/admin/services/` como alias
- [x] 8.4 Verificar ruff en archivos modificados
