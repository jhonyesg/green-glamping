# Design: Plans y media en base de datos

## Context

El bot de Green Glamping tiene sus precios hardcodeados en
`multibot/data/seeds/green_glamping_kb.json` (campo `response_text` del
intent `precio_general` — `$290.000`, etc.). Las imágenes viven en
`multibot/data/clients/green-glamping/media/images/` y los audios en
`media/audios/`, sin estar referenciados desde ningún intent. Para
cambiar un precio hay que: editar el JSON → correr el script de seed
→ el bot recién refleja el cambio en el próximo request. No hay
panel admin para editar nada, ni manera de que un intent arme su
respuesta a partir de datos vivos.

Hay además un choque de nombres a resolver: el modelo SQLAlchemy
`app/models/plan.py` ya existe y representa el **plan de suscripción
del SaaS** (monthly_price, max_concurrent_chats) en el schema
`public`. El nuevo modelo de catálogo de servicios del cliente debe
llamarse distinto (sugerido: `service_plan` o `offering`) y vive en
el schema del tenant.

El storage de media local se hace en
`multibot/data/uploads/<tenant_slug>/<key>.<ext>`, servido por
FastAPI con `StaticFiles` montado en `/media/`.

## Goals / Non-Goals

**Goals:**
- Catálogo de planes/servicios editable desde panel, persistido en
  la BD del tenant, sin redeploy.
- Biblioteca de archivos multimedia con keys referenciables desde
  los templates de respuesta.
- Renderizado de templates Jinja con contexto (planes, media, memoria)
  integrado en el pipeline sin romper el comportamiento actual.
- Seed que migre los datos actuales (precios del JSON, imágenes en
  disco) hacia la BD.
- 100% retrocompatible: intents sin `response_template` siguen
  funcionando como antes.

**Non-Goals:**
- Clasificación con LLM, auto-mejora, dashboard de patrones
  (cambio posterior `intents-inteligentes`).
- Editor visual de intents (cambio posterior `editor-de-intents`).
- Multi-idioma, versionado de planes, CDN/S3.
- Cambiar la UI existente del bot (Canales, Flujo, Simulador).

## Decisions

### Decisión 1: Modelo de BD nuevo se llama `offering`, no `plan`

**Por qué:** el modelo `app/models/plan.py` ya existe y representa
planes de suscripción SaaS en `public.plans`. Reutilizar el nombre
causaría colisión. El nombre semánticamente correcto para "combo de
servicios que ofrece el cliente" es `offering` (producto/servicio
ofrecido).

**Alternativa considerada:** renombrar el `Plan` SaaS a
`SubscriptionPlan`. Descartado: es un cambio que rompe código
existente (`app/notifications/...`, seeds previos) sin beneficio
inmediato. La nueva tabla `offering` evita el conflicto sin tocar
nada de lo anterior.

### Decisión 2: Schema de las tablas = schema del tenant (no `public`)

`plans-catalog` y `media-library` viven en
`tenant_<slug>.offering` y `tenant_<slug>.media`, igual que
`kb_intents`. Razón: cada cliente tiene su propio catálogo; no se
comparten entre tenants. Sigue la convención multi-tenant del
proyecto (ver `app/models/conversation.py`).

### Decisión 3: `response_type` como columna nueva en `kb_intents`

Tres valores:
- `static` (default, retrocompatible): usa `response_text` como hoy.
- `template_jinja`: usa `response_template` con Jinja, contexto
  `{ plans, media, recent_turns, user, channel }`.
- `data_driven`: igual a `template_jinja` pero requiere `requires_data`
  no vacío (ej: `requires_data = ["plans"]`); el render falla ruidoso
  si falta.

**Alternativa:** mantener todo en un único campo `response_text` y
detectar `{{ ... }}` para inferir. Descartado: ambiguo, hace
imposible desactivar el rendering por intent, y mete Jinja en
campos que deberían ser texto plano.

### Decisión 4: Storage local en `data/uploads/`, servido por FastAPI

`POST /admin/media/upload` guarda en
`data/uploads/<tenant_slug>/<sha256>.<ext>` (nombre por hash para
evitar colisiones y sanitizar nombres). FastAPI monta
`/media/<tenant_slug>/<filename>` como `StaticFiles`.

**Por qué no S3/Cloudinary:** son dependencia externa y costo. Para
un solo cliente piloto, disco local alcanza (límite sugerido 50 MB
por archivo, 500 MB por tenant, validado en el endpoint).

**Migración futura:** cuando se sume CDN, se reemplaza el `path`
relativo por URL completa; el render y el bot no cambian.

### Decisión 5: Sandboxing estricto de Jinja

`jinja2.Template` permite ejecución de código si no se acota. Se
usa `jinja2.sandbox.SandboxedEnvironment` con un loader
`DictLoader` que solo conoce los templates provistos. Variables
expuestas: dicts y dataclasses inmutables, no objetos de BD
directos (mapeo explícito `Offering → {nombre, precio, descripcion,
incluye}` para evitar exponer columnas internas).

**Filtros custom:**
- `currency_cop(value)`: formatea `290000` → `"$290.000"`.
- `media_url(key)`: resuelve `media[key]` → URL pública.
- `today_es()`: fecha actual en español (para mensajes dinámicos).

### Decisión 6: Seed como comando idempotente

`scripts/seed_green_glamping.py` se extiende con dos nuevas
funciones (`seed_plans()`, `seed_media()`) ejecutadas después del
seed actual de intents. Cada una detecta si ya existe y omite
(operación upsert por `slug`/`key`). El seed total se puede correr
N veces sin duplicar datos.

**Para el seed inicial de media:** los 10 JPG en
`multibot/data/clients/green-glamping/media/images/` se copian a
`data/uploads/green-glamping/` y se insertan filas con
`source='seed'`, `original_path` apuntando al archivo viejo
(referenciado para auditoría, no usado en runtime).

### Decisión 7: Orden de tareas (mínima disrupción)

1. Migración Alembic (tablas vacías, no rompe nada).
2. Modelos + helpers (sin uso aún).
3. APIs admin + forms (accesibles pero sin uso desde el bot).
4. Seed inicial (puebla datos de prueba).
5. Integración con pipeline (renderizado activado, retrocompatible).
6. Migrar `response_text` de `precio_general` a `template_jinja`
   para que el primer intent use el nuevo sistema (prueba E2E).
7. Tests + verificación.

El paso 6 es el único que **cambia comportamiento observable**.
Todo lo demás es aditivo.

## Risks / Trade-offs

**[R1] Quiebre del seed existente al extenderlo**
→ El script `seed_green_glamping.py` actual borra y reinserta
`kb_intents`. Si alguien lo corre durante el cambio, se pierden
personalizaciones manuales. Mitigación: el nuevo seed distingue
`source='manual'` de `source='seed'` y solo borra/reescribe los
segundos.

**[R2] Templates Jinja escritos por admin con errores**
→ Un template mal escrito puede tumbar el pipeline. Mitigación:
"preview" obligatorio en el form admin antes de guardar + tests de
renderizado con fixtures. Si el render falla en runtime, fallback
automático al `response_text` estático con un log de warning.

**[R3] Storage crece sin control**
→ Sin cuota, un admin podría subir GB de imágenes. Mitigación: límite
de 50 MB por archivo, validación de MIME, y log del total por
tenant. Una limpieza periódica de archivos huérfanos (no
referenciados desde ningún offering/intent) queda como tarea
documentada en `docs/canales.md` para una iteración posterior.

**[R4] Cambio de schema de `kb_intents` puede ser disruptivo**
→ Agregar columnas nuevas es seguro en Postgres (con DEFAULT), pero
el cambio del `response_text` a opcional + nuevo `response_template`
puede confundir queries existentes. Mitigación: `response_text`
sigue siendo NOT NULL; `response_template` y `response_type` son
nuevos con default sensato.

**[R5] Colisión de nombres con `app/models/plan.py`**
→ Ya tratado (Decisión 1). Documentado en el design para que el
implementador no caiga en la trampa.

## Migration Plan

**Pre-deploy:** ninguna acción (los cambios son aditivos).

**Deploy:** ejecutar `alembic upgrade head` para crear las tablas
`offering` y `media` en todos los schemas de tenant. Sin downtime.

**Post-deploy:**
1. Correr `python -m scripts.seed_green_glamping` para poblar
   planes/media iniciales.
2. Verificar en `/admin/plans` que aparecen los 5 planes actuales
   de Green Glamping.
3. Activar el `response_type='template_jinja'` en
   `precio_general` (operación manual via panel o script).
4. Mandar un "cuánto cuesta" de prueba al bot y verificar que
   la respuesta se arma desde la BD.

**Rollback:** `alembic downgrade -1` borra las tablas. Como
ningún intent fue migrado a `template_jinja`, no hay pérdida de
datos. Si ya se migró `precio_general`, revertir manualmente su
`response_type` a `static`.

## Open Questions

1. **¿Los planes deben tener vigencias?** (ej: precio válido
   desde/hasta). Por ahora no, pero la columna `metadata jsonb` lo
   permite agregar sin migración.
2. **¿El bot debe recordar el último plan visto por usuario?**
   (para "el combo 5 del que me hablaste"). Eso requiere
   `conversation.state.last_offering_id` y es scope de
   `intents-inteligentes`, no de este cambio.
3. **¿Multi-imagen por plan?** Sí — un plan puede tener galería
   (portada + fotos adicionales). En este cambio soportamos
   `imagen_id` única (portada). Galería es scope futuro.
