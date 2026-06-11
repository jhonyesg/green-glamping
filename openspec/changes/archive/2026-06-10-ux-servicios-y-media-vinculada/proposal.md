# Proposal: UX — Servicios, key auto-generada, media vinculada

## Why

El cambio `plans-y-media-en-bd` quedó funcional pero con fricción UX
en tres puntos que el superadmin detectó al usarlo:

1. La columna del catálogo se llama "Planes" — confunde con los
   planes de suscripción SaaS (`app/models/plan.py`). El dueño del
   negocio lo llama mentalmente "los servicios que ofrezco".
2. La **key** de la media la ingresa el usuario. Es un campo
   técnico que aporta poco valor y se presta a typos / duplicados.
3. La imagen de portada del servicio y las imágenes/audios que se
   mandan con una respuesta del bot viven en dos lugares
   desconectados: una se sube desde el form del servicio, otras
   desde la biblioteca. El admin no puede decir "este audio va con
   esta respuesta" sin hardcodear `file_id`s en código.

**Nota importante — alcance del catálogo:** la plataforma **no
gestiona precios ni transacciones**. El catálogo de "Servicios"
es informativo: cada item describe qué ofrece el negocio (nombre,
descripción, qué incluye, imagen referenciada). El cierre
comercial, el cobro y la facturación ocurren por fuera — entre
el dueño del negocio y el cliente, en el momento y por el canal
que ellos decidan. Por eso este catálogo no tiene columna de
precio: confundir al admin con un campo de monto que la
plataforma no procesa sería peor que no tenerlo.

## What Changes

- **Renombrar** la etiqueta UI de "Planes" a "Servicios" (sidebar,
  títulos, forms, breadcrumbs). La tabla `offering` y la ruta
  `/admin/plans/` **se mantienen** por compatibilidad — el cambio
  es solo cosmético de cara al admin. La página `/admin/plans/`
  ahora dice "Servicios" y `/admin/media/` sigue como "Media".
- **Key auto-generada** en upload de media: el sistema asigna
  `media_<NNN>` (monotónico por tenant) y deriva el nombre del
  archivo para mostrarse. El campo `key` se mantiene en la BD
  para referencias desde templates, pero el admin **ya no lo
  ingresa**. Si quiere un slug semántico, lo renombra desde el
  form de edición.
- **Selector de media en servicios**: en `/admin/services/{id}/edit`
  (URL nueva, redirige desde la vieja), en vez de subir imagen
  propia, se elige de la biblioteca de media del tenant. La subida
  de imágenes se hace una sola vez en `/admin/media/`.
- **Vinculación de media a intents**: en el editor de intents
  (existente o nuevo según la implementación), cada intent puede
  declarar 0..N archivos de media que se adjuntan automáticamente
  cuando ese intent matchea. Se reutiliza el campo
  `kb_intents.response_audio_id` existente y se agrega
  `kb_intents.response_media_ids` (jsonb) para múltiples archivos.

## Capabilities

### New Capabilities

- `services-ux-rename`: el catálogo de planes se muestra como
  "Servicios" en toda la UI del panel admin (sidebar, títulos,
  forms, breadcrumbs). Tabla interna sigue llamándose `offering`.
- `media-auto-key`: la `key` de un archivo subido se genera
  automáticamente (`media_<NNN>`). El admin puede renombrarla
  desde el form de edición para algo semántico, pero no la
  ingresa en el upload.
- `media-linked-to-intents`: cada intent puede tener 0..N media
  adjuntos. La pipeline los envía cuando el intent matchea. El
  editor permite elegirlos de la biblioteca del tenant.

### Modified Capabilities

_Ninguna._ Los capabilities nuevas son aditivas. La tabla
`offering`, los endpoints existentes, y el comportamiento de la
pipeline no cambian (solo se agregan campos opcionales).

## Impact

- **Templates admin**: `plans/index.html`, `plans/edit.html` →
  renombrar etiquetas a "Servicios". Agregar selector de media
  en vez de upload.
- **Rutas admin**: `/admin/plans/*` se mantiene como URL
  (compatibilidad con bookmarks). Agregar alias
  `/admin/services/` que apunta al mismo handler. Migrations no
  necesarias.
- **Rutas media**: `app/admin/routes/media.py` cambia el form de
  upload: sin campo `key`. Auto-genera `media_<NNN>` (siguiente
  número disponible por tenant).
- **Modelo `KBIntent`**: agregar columna `response_media_ids`
  (jsonb, default `[]`). Migración 004.
- **Rutas intents**: `app/admin/routes/kb.py` extiende el form
  con un selector de media. Si se reutiliza el form existente,
  el cambio es chico. Si se requiere un editor nuevo, queda
  documentado en `design.md` con la decisión.
- **Pipeline**: si el intent matcheado tiene `response_media_ids`,
  la pipeline los adjunta a `OutboundMessage` (texto + archivos).
  Cambia el shape del `PipelineResult` para que `webhook` sepa qué
  enviar.
- **Tests**: actualizar `test_plans_media_integration.py` para
  reflejar la key auto-generada. Agregar test de media vinculada
  a intent.

## Out of scope (cambios futuros)

- Editor visual dedicado de intents (cambio `editor-de-intents`).
- Galería multi-imagen por servicio.
- Auto-rename inteligente de keys por contenido del archivo.
