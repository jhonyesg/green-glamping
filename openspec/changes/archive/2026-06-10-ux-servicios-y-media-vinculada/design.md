# Design: UX — Servicios, key auto-generada, media vinculada

## Context

El cambio `plans-y-media-en-bd` dejó el catálogo de planes y la
biblioteca de media funcionales. Tres fricciones detectadas al
usar el panel:

1. La UI mezcla el concepto "planes de suscripción SaaS" con
   "servicios que ofrece el negocio" — el admin lo piensa como
   "lo que ofrezco", no como "planes".
2. El campo `key` en el upload de media es técnico. El admin
   tiene que inventar un identificador que no choque con los
   existentes. Un usuario no técnico prefiere no verlo.
3. La imagen de portada del servicio se sube en el form del
   servicio, pero las imágenes/audios que la pipeline adjunta a
   las respuestas de un intent se suben en `/admin/media/`. Dos
   flujos desconectados. No hay forma de decir "este audio va
   con la respuesta del intent de info general" sin hardcodear
   en el template Jinja.

## Goals / Non-Goals

**Goals:**
- Etiqueta "Servicios" en toda la UI del catálogo (sidebar,
  títulos, forms). Tabla interna y URL siguen siendo
  `offering` / `/admin/plans/` para no romper bookmarks.
- Upload de media sin campo `key` visible. La key se genera
  automáticamente como `media_NNN` (siguiente entero disponible
  por tenant). El admin puede renombrarla en el form de
  edición a algo semántico (`carta_bebidas`, etc.) si quiere.
- Imagen de portada del servicio se elige de la biblioteca de
  media (selector), no se sube en el form del servicio.
- Cada intent puede declarar 0..N media adjuntos. La pipeline
  los envía automáticamente cuando el intent matchea. Se
  editan desde `/admin/kb/{id}` (extensión del form existente).

**Non-Goals:**
- Renombrar la tabla `offering` o cambiar la URL `/admin/plans/`.
- Editor visual de intents estilo n8n (cambio
  `editor-de-intents`, próximo).
- Galería multi-imagen por servicio.
- Hash automático de contenido para deduplicar uploads (un
  mismo archivo subido 2 veces se guarda 2 veces; el sha256
  ya está en el path pero no se deduplica).
- Drag & drop de archivos en el upload.

## Decisions

### Decisión 1: "Planes" → "Servicios" sin tocar schema ni URLs

La tabla se llama `offering`, la ruta es `/admin/plans/`. Solo
cambia el texto visible al admin:
- Sidebar: `🛎 Servicios` (en vez de `📋 Planes`).
- Título de página: "Servicios del catálogo".
- Forms: "Nuevo servicio", "Editar servicio", etc.
- Breadcrumbs: "Canales › Servicios".
- La pestaña `/admin/media/` sigue llamándose "🖼 Media".

**Razón:** la nomenclatura interna es estable y los templates
existentes no se rompen. El cambio es 100% de copy en strings.

**Alternativa:** renombrar la tabla a `services`. Descartado:
sería una migración destructiva y rompería el seed y todos los
referencias. El cambio de copy logra el mismo objetivo UX.

### Decisión 2: Key auto-generada como `media_NNN`

Al subir, el sistema calcula el siguiente entero disponible
para ese tenant:

```python
# Pseudo
next_n = max(int(k.split("_")[1]) for k in keys_matching("media_%")) + 1
new_key = f"media_{next_n:03d}"
```

El admin puede renombrarla a algo semántico en el form de
edición (`carta_bebidas`, `portada_combo_5`, etc.). El
`UniqueConstraint` actual sobre `key` se mantiene — la
generación es atómica y verifica colisiones.

**Por qué no usar el nombre del archivo:** dos archivos
`IMG_2024.jpg` consecutivos chocarían. El índice monotónico
es seguro.

**Por qué no usar sha256 del contenido:** el admin no puede
memorizar un sha256. La key legible es la que usa en templates;
si quiere semántica, la renombra después.

**Por qué no dejar de tener key:** la key es la referencia
estable desde templates Jinja (`{{ 'carta' | media_url }}`).
Cambiar el nombre del archivo no debe romper la referencia.

### Decisión 3: Imagen de servicio = selector de media library

El form de edición de servicio tiene un dropdown con todos los
media activos del tenant (imágenes únicamente). Al guardar,
`offering.imagen_id` se setea al id elegido. La columna
`imagen_id` ya existe (migración 002). No requiere nueva
migración.

Eliminamos el endpoint `POST /admin/plans/{id}/upload-image` y
el form de upload que tenía. Si el admin quiere subir una
nueva imagen, va a `/admin/media/` primero y después vuelve al
servicio a seleccionarla.

**Por qué no un upload embebido con auto-promoción a media:**
duplica el form de upload en dos lugares. Una sola biblioteca,
un solo lugar para subir.

**Trade-off:** dos clicks en vez de uno. Pero la consistencia
es mayor: el admin sabe dónde están todos los archivos.

### Decisión 4: Media adjunta a intents — campo `response_media_ids`

`kb_intents` ya tiene `response_audio_id` (single). Agregamos
`response_media_ids` (jsonb, default `[]`) para múltiples
archivos. La pipeline los adjunta a la respuesta cuando el
intent matchea.

**Migración 004:** agregar columna. Backfill: si
`response_audio_id` está set, agregarlo al array.

**Por qué campo nuevo en vez de reutilizar el existente:** el
campo viejo es single y es audio específicamente. La realidad
es que un intent puede querer enviar 1 foto + 1 PDF + 1 audio.
jsonb con ids es la solución más flexible.

**Por qué la pipeline debe cambiar:** hoy el `OutboundMessage`
es texto o media única. Para múltiples, o se cambia el shape
del `OutboundMessage` (agregar `media_attachments: list[int]`)
o se envía texto + un `OutboundMessage` por cada media. La
opción más limpia es agregar `media_attachments` al
`OutboundMessage` y que el `OutboundMessage` actual de la
pipeline solo use el primero como "media principal" (foto),
mientras que el `webhook` itere sobre los adjuntos.

### Decisión 5: Editor de media adjunta en `/admin/kb/{id}`

El form de edición de intents tiene ahora un multi-select
con todos los media activos del tenant. Al guardar, el array
se persiste en `response_media_ids`. La vista previa del
intent muestra las miniatura de cada media adjunto.

**Por qué extender el form existente y no crear un editor
nuevo:** el form de `/admin/kb/{id}` ya tiene todos los campos
del intent (keywords, response_text, priority, handoff). Es el
lugar natural. Un editor separado (estilo `editor-de-intents`)
es scope de un próximo OpenSpec.

**Trade-off conocido:** la vista de lista `/admin/kb/` no
muestra los media adjuntos. Solo se ven al abrir el detalle.
Mejora futura: columna "N media adjuntos" en la lista.

## Risks / Trade-offs

**[R1] Números `media_NNN` se "gastan" si se borra una media**
→ Si el admin borra la media con `key=media_005`, el siguiente
upload puede ser `media_006` (no `media_005` de nuevo). El
"gap" es inofensivo pero confunde. Mitigación: el `_NNN` se
calcula con `MAX + 1`, no con "siguiente libre". Si el admin
quiere un nombre más limpio, lo renombra.

**[R2] Renombrar la key puede romper templates que la referencian**
→ Si un template dice `{{ 'media_005' | media_url }}` y el
admin renombra la key a `carta_bebidas`, el template devuelve
vacío. Mitigación: en el form de edición, si se renombra la
key, mostrar warning "Esta key está siendo usada en N
templates. Actualízalos si renombras." (Mejora futura, no
incluida en este cambio.)

**[R3] Selector de media en servicio crece mucho**
→ Con 100+ archivos, el dropdown se vuelve difícil de usar.
Mitigación v1: search box sobre la lista. Mitigación v2:
HTMX async search. Para este cambio: orden por fecha desc +
máximo 200 visibles + "cargar más" si hace falta.

**[R4] Cambio de `OutboundMessage` rompe consumers existentes**
→ El campo `media_attachments` es opcional. Consumers que solo
leen `text` no cambian. Los webhooks de Telegram/WhatsApp ya
manejan media única (campo `file_id`/`media_id`); el webhook
telegram itera y envía un mensaje por adjunto si el adapter
lo soporta.

**[R5] Cambio de "Planes" a "Servicios" confunde si alguien
ya se acostumbró a la otra etiqueta**
→ Los textos del seed, docs y changelog se mantienen con la
palabra "planes" (internamente). Solo la UI cambia. El admin
lo lee una vez y se acostumbra.

## Migration Plan

**Pre-deploy:** ninguno.

**Deploy:**
1. Merge del código.
2. Correr `alembic upgrade head` (aplica migración 004 que
   agrega `response_media_ids`).
3. Sin downtime: la columna es nueva y con default `[]`.

**Post-deploy:**
1. Verificar en `/admin/services/`: la UI dice "Servicios".
2. Ir a `/admin/media/`, subir un archivo: la key se
   genera automáticamente y se muestra como `media_001`.
3. Renombrarla a algo semántico (ej: `carta_bebidas`).
4. Ir a `/admin/services/{id}/edit`, elegir la imagen de
   portada del selector.
5. Ir a `/admin/kb/{id}`, agregar 1-2 media adjuntos al
   intent informativo del cliente (ej: `info_servicios`).
6. Probar el bot: la respuesta de ese intent debe llegar con
   los adjuntos.

**Rollback:** `alembic downgrade 003` borra la columna. La UI
vuelve a pedir key en upload (con un fallback). Sin pérdida
de datos.

## Open Questions

1. **¿El selector de media debe filtrar por tipo?** Hoy el
   form de servicio pide solo imágenes. ¿Filtramos a
   `tipo='image'` o mostramos todos y el admin decide?
   → Por ahora: solo imágenes en el selector de servicio.
   Mejora futura si surge la necesidad.
2. **¿Multi-idioma para "Servicios"?** El admin podría
   querer "Servicios" / "Services" según el tenant. No se
   hace en este cambio — los demás textos del panel ya están
   en español hardcoded.
3. **¿Notificar al admin si renombra una key usada?** Warning
   suave, no blocker. Implementación queda como tarea
   documentada (no en este cambio).
