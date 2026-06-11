# Proposal: Plans y media en base de datos

## Why

Los precios, las imágenes del portafolio y los audios del cliente
Green Glamping viven en archivos JSON estáticos y en carpetas de
imágenes sueltas, sin fuente de verdad en la base de datos. Para
actualizar el precio de un combo hay que editar el JSON, correr el
script de seed y reiniciar el bot. Para enviar una imagen con una
respuesta hay que hardcodear el `file_id` en código. No hay forma
de que un intent arme su respuesta a partir de datos vivos (planes,
media), ni de que el admin edite nada sin tocar el repositorio.

## What Changes

- **Tabla `plans`** en el schema del tenant: catálogo editable de
  planes/servicios con `nombre`, `precio_cop`, `descripcion`,
  `imagen_id` (FK a media), `incluye` (jsonb), `display_order`,
  `is_active`.
- **Tabla `media`** en el schema del tenant: biblioteca de archivos
  con `key` única, `tipo` (image|audio|document), `path` en disco,
  `descripcion`, `is_active`.
- **Form admin** `/admin/plans` con CRUD (crear, listar, editar,
  activar/desactivar) + upload de imagen referenciada.
- **Form admin** `/admin/media` con CRUD + upload.
- **Migración Alembic** que crea ambas tablas.
- **Seed inicial**: importa desde `multibot/data/clients/green-glamping/`
  los datos actuales (intents con precios hardcodeados, imágenes en
  disco) hacia la BD, con `data_migrated_from` en metadata.
- **Renderizado de templates Jinja** en el pipeline: cada intent
  puede tener `response_type` (`static` | `template_jinja` |
  `data_driven`) y `response_template` con placeholders. El render
  recibe como contexto: planes activos, media por key, recent_turns.
- **Endpoint de upload** `POST /admin/plans/{id}/upload-image` y
  `POST /admin/media/upload` con almacenamiento en `data/uploads/`.
- **API JSON** `GET /api/plans` y `GET /api/media/{key}` para uso
  interno (pipeline, simulador).
- **Retrocompatibilidad**: si un intent NO tiene `response_template`,
  se usa el `response` actual (string estático). No hay breaking changes.

## Capabilities

### New Capabilities

- `plans-catalog`: catálogo editable de planes/servicios del tenant
  con precios, descripciones e imágenes referenciadas.
- `media-library`: biblioteca versionable de archivos (imágenes,
  audios, documentos) con keys únicas referenciables desde los
  templates de respuesta.
- `template-rendering`: motor de plantillas Jinja embebido en el
  pipeline que arma respuestas a partir de datos vivos (planes,
  media, memoria de conversación).

### Modified Capabilities

_Ninguna._ Este cambio introduce capacidades nuevas sin modificar
requisitos de specs existentes. El comportamiento del pipeline sigue
siendo compatible: si un intent no define `response_type` o
`response_template`, el `response` estático se usa como antes.

## Impact

- **Modelos nuevos** (SQLAlchemy): `app/models/plan.py`,
  `app/models/media.py`.
- **Migración Alembic**: nueva revisión con las 2 tablas.
- **Rutas admin nuevas**: `app/admin/routes/plans.py`,
  `app/admin/routes/media.py`.
- **Templates nuevos**: `app/admin/templates/plans/`,
  `app/admin/templates/media/`.
- **Pipeline**: `app/bot/pipeline.py` consulta el `response_type`
  del intent y, si es `template_jinja` o `data_driven`, renderiza
  con `jinja2.Template` antes de devolver.
- **Helpers nuevos**: `app/core/template_render.py` (motor de
  rendering con contexto seguro), `app/core/media_store.py`
  (storage en disco + URLs públicas).
- **Seed**: `scripts/seed_green_glamping.py` extendido con funciones
  para poblar `plans` y `media` desde los datos actuales.
- **Tests nuevos**: `tests/test_template_rendering.py`,
  `tests/test_plans_crud.py` (con DB transaccional).
- **Almacenamiento**: nuevo directorio `data/uploads/` (gitignored)
  para archivos subidos.

## Out of scope (cambios futuros)

- `intents-inteligentes`: clasificación con memoria de conversación,
  fallback con LLM pequeño, auto-mejora con sugerencias. **Requiere
  este cambio** porque los templates referencian planes/media que
  deben existir en BD.
- `editor-de-intents`: UI para editar keywords y templates con
  preview en vivo. **Requiere este cambio** porque el editor se
  monta sobre la tabla `kb_intents` extendida.
- Multi-idioma en planes/media (campo `locale`).
- CDN/S3 para `media.path` (hoy es local).
