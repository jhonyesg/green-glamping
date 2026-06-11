# Plans y Media — Guía de operación

> Changes: `plans-y-media-en-bd`, `ux-servicios-y-media-vinculada`. Estado: implementado.

## Resumen

Cada tenant tiene su propio catálogo de **Servicios** y su
**biblioteca de media** (imágenes, audios, PDFs). Todo persiste
en la BD del schema del tenant, se edita desde el panel admin y
se referencia desde los templates de respuesta con Jinja y desde
los intents como adjuntos.

**Importante:** la plataforma **muestra los precios pero no
procesa pagos**. El campo `precio_cop` en cada servicio es
informativo — el dueño del negocio lo edita, el bot lo muestra
en las respuestas, y el cliente paga por fuera (Nequi, Daviplata,
Davivienda, BBVA, Bold/PSE). El cierre comercial es entre el
dueño y el cliente, por el canal que ellos prefieran.

## Catálogo sembrado (Green Glamping)

El seed `scripts/seed_green_glamping.py` carga 13 servicios
reales basados en el dataset del cliente:

| Slug | Nombre | Precio desde | Imagen |
|---|---|---|---|
| `solo_vuelo` | Solo vuelo / cumple / aniversario | $30.000 | — |
| `combo_glamping` | Glamping + Parapente | $200.000 | `glamping_montana` |
| `combos_1_a_7_1` | Combo 1 — Aventura Glamping | $160.000 | `combo_7_glamping` |
| `combos_1_a_7_2` | Combo 2 — Aniversario Romántico | $160.000 | `spa_pareja` |
| `combos_1_a_7_3` | Combo 3 — Cumpleaños Inolvidable | $160.000 | `decoracion_cumpleanos` |
| `combos_1_a_7_4` | Combo 4 — Desconexión Total | $160.000 | `glamping_descripcion` |
| `combos_1_a_7_5` | Combo 5 — Experiencia Completa | $290.000 | `vista_glamping_montana` |
| `combos_1_a_7_6` | Combo 6 — Glamping + Adrenalina | $160.000 | `portafolio_glamping` |
| `combos_1_a_7_7` | Combo 7 — Glamping Premium Cristal | $160.000 | `glamping_montana` |
| `parapente_individual` | Parapente individual | $220.000 | `portafolio_parapente` |
| `spa_pareja` | Spa pareja con jacuzzi | $130.000 | `spa_pareja` |
| `transporte_chipaque` | Transporte desde Chipaque | $60.000 | — |
| `carta_restaurante` | Carta del restaurante | $0 | `carta_bebidas` |

El admin puede **editar cualquier campo** desde `/admin/plans/`
incluyendo nombre, descripción, precio, orden, imagen vinculada,
y activar/desactivar.

**Reset completo** (útil después de pruebas):
```bash
python -m scripts.seed_green_glamping --clean
```

Borra servicios/media de prueba, copia las imágenes del dataset
con keys semánticas (`glamping_montana`, `spa_pareja`, etc.) y
siembra los 13 servicios arriba.

**Solo añadir** (idempotente, sin tocar lo existente):
```bash
python -m scripts.seed_green_glamping
```

## Cómo editar precios

1. Login como superadmin.
2. `/admin/plans/?tenant=green-glamping`.
3. Click ✎ en el servicio a editar.
4. Cambiar el campo **"Precio desde (COP)"**.
5. Click "Guardar".

El cambio se refleja al instante en la próxima respuesta del
bot (sin reiniciar el servidor). La plantilla de respuesta
del intent `precio_general` está migrada a template Jinja
que itera `plans` — los precios siempre vienen de la BD.

## Desactivar vs Eliminar (servicios y media)

Ambos objetos tienen **dos formas de borrado**, según el caso:

| Acción | Botón | Para qué sirve | Reversible |
|---|---|---|---|
| 🗑 **Desactivar** (soft) | Form a `/deactivate` | Cosas que vuelven por temporada (ej: combo de San Valentín, imagen de un evento) | Sí — `is_active=false`, sigue en BD; reactivar editando y marcando "Activo" |
| ❌ **Eliminar** (hard) | Form a `/delete` | Errores de carga, servicios que ya no se ofrecen nunca más, archivos duplicados | **No** — la fila se borra; en media, también se borra el archivo del disco |

**Regla práctica:** si dudás, **desactivá**. Si estás 100%
seguro de que no vuelve, **eliminá**. El botón ❌ tiene
confirmación explícita "DEFINITIVAMENTE" para evitar clicks
accidentales.

Para media, la eliminación también borra el archivo físico de
`data/uploads/<tenant>/<sha>.<ext>`. Si el archivo no se puede
borrar del disco, la operación sigue siendo exitosa en BD (el
log de la operación se ve en consola).

## Cómo vincular imagen a un servicio

1. Si la imagen todavía no está en la biblioteca: ir a
   `/admin/media/?tenant=…` y subirla. La **key se asigna
   automáticamente** (`media_NNN`). El admin puede renombrarla.
2. Volver a `/admin/plans/{id}/edit`. En la columna derecha,
   elegir del selector "Imagen de portada".
3. Guardar.

La miniatura aparece en el listado de servicios.

## Estructura

```
panel admin:
  /admin/plans/             ← alias semántico /admin/services/
  /admin/plans/{id}/edit    ← edición + selector de imagen
  /admin/media/             ← biblioteca (upload múltiple, key auto)
  /admin/kb/{id}            ← editor de intents con media adjuntos
  /api/plans?tenant=X       ← JSON servicios activos
  /api/media/{slug}/{key}   ← JSON URL pública de un media

BD (schema tenant_<slug>):
  offering                  ← catálogo de servicios (sin precio)
  media                     ← biblioteca de archivos

Disco:
  data/uploads/<slug>/<sha>.<ext>   ← archivos físicos
```

## Panel: crear un servicio

1. Login como superadmin.
2. `http://localhost:8000/admin/plans/?tenant=green-glamping`.
3. Formulario "Nuevo servicio":
   - **slug**: `combo_glamping` (sin espacios, snake_case, único).
   - **nombre**: "Glamping + Parapente".
   - **descripcion**: línea corta.
   - **qué incluye**: uno por línea.
   - **display_order**: menor = aparece primero.
   - **is_active**: marcado = visible.
4. Click "Crear servicio".

**Nota:** la columna de precio fue removida del catálogo. La
plataforma no maneja montos; el dueño negocia directo con el
cliente.

## Panel: imagen de portada del servicio

La imagen **no se sube** en el form del servicio. Se elige de
la biblioteca de media:

1. Si todavía no subiste la imagen, andá a
   `/admin/media/?tenant=…` y subí el archivo. La **key se
   genera automáticamente** (`media_001`, `media_002`, …).
   Podés renombrarla después.
2. Volvé a `/admin/plans/{id}/edit`. En la columna derecha,
   sección "Imagen de portada", elegí del selector.
3. Click "Guardar imagen".

## Panel: biblioteca de media

`/admin/media/?tenant=…`:
- Click "Elegir archivo" + "Subir".
- La key se asigna automáticamente (`media_NNN`).
- Las imágenes aparecen con miniatura en el grid.
- Desactivar = ocultar (no borra el archivo).

## Panel: media adjuntos a un intent

Cada intent puede tener 0..N archivos de media adjuntos que se
mandan automáticamente cuando el intent matchea:

1. `/admin/kb/?tenant=…` → click en un intent existente.
2. En el form, scroll hasta "🖼 Media adjuntos a esta respuesta".
3. Multi-select con todos los media activos del tenant.
4. Mantené Ctrl/Cmd presionado para seleccionar varios.
5. Guardar.

## Templates de respuesta (Jinja)

Campo `response_type` agregado a `kb_intents`:

| Campo | Default | Notas |
|---|---|---|
| `response_type` | `"static"` | `static` / `template_jinja` / `data_driven` |
| `response_text` | (requerido) | Texto plano. Fallback si el render falla. |
| `response_template` | NULL | Template Jinja2. Si está, se renderiza. |
| `requires_data` | NULL | Lista de claves requeridas (data_driven). |
| `response_media_ids` | `[]` | Lista de ids de media a adjuntar. |

### Filtros y funciones Jinja

| Nombre | Tipo | Ejemplo | Resultado |
|---|---|---|---|
| `currency_cop` | filtro | `{{ 290000 \| currency_cop }}` | `$290.000` |
| `media_url` | filtro | `{{ 'carta' \| media_url }}` | `/media/.../abc.jpg` o `""` |
| `today_es` | global | `{{ today_es() }}` | `10 de junio de 2026` |

### Sandbox

Render con `jinja2.sandbox.SandboxedEnvironment`. Bloqueado:
- Atributos con `_` o `__` (ej: `_sa_instance_state`).
- `{% import %}` de módulos arbitrarios.

Si el admin escribe un template roto, **el bot no se cae**:
hace fallback a `response_text` y loggea `template_render_failed`.
Ver `app/core/template_render.py`.

## Migraciones

```bash
cd multibot
.venv/bin/alembic upgrade head

# Rollback
.venv/bin/alembic downgrade -1
```

- `001`: schema `public` con `plans` (SaaS) y `tenants`.
- `002`: tablas `offering` y `media` en cada schema `tenant_*`.
- `003`: `response_type`, `response_template`, `requires_data` en `kb_intents`.
- `004`: `response_media_ids` (jsonb) en `kb_intents` + backfill desde `response_audio_id`.

## Seed inicial

```bash
.venv/bin/python -m scripts.seed_green_glamping
```

Carga los 6 servicios base de Green Glamping y copia las 10
imágenes a `data/uploads/green-glamping/<sha>.jpg`. **Idempotente.**

## Endpoints API

| Método | Ruta | Uso |
|---|---|---|
| GET    | `/api/plans?tenant=X`              | JSON con servicios activos |
| GET    | `/api/media/{slug}/{key}`          | JSON con URL pública |
| GET    | `/media/{slug}/{archivo}`          | Sirve archivo estático |

## Smoke test E2E

```bash
alembic upgrade head
python -m scripts.seed_green_glamping
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

1. Login → `/admin/plans/` debe decir "🛎 Servicios del catálogo".
2. Click ✎ en un servicio → selector de imagen sin upload propio.
3. `/admin/media/` → subir archivo → la key se asigna auto.
4. `/admin/kb/{id}` → multi-select de media adjuntos.
5. El bot responde con la media adjunta.

## Troubleshooting

| Problema | Causa probable | Solución |
|---|---|---|
| `/api/plans` devuelve 500 `relation "offering" does not exist` | Migración 002 no aplicada | `alembic upgrade head` |
| `media_url('xxx')` devuelve vacío | La key no existe o `is_active=false` | Verificar en `/admin/media` |
| Template muestra `{{ p.nombre }}` literal | `response_type` no es `template_jinja` en BD | Verificar columna en `tenant_<slug>.kb_intents` |
| 500 al subir imagen | Permisos de `data/uploads/` | `chmod -R 755 multibot/data/uploads/` |
| Media adjuntos no se envían | El intent no tiene `response_media_ids` o la media está desactivada | Re-editar el intent, verificar en BD |
| Sidebar dice "Planes" en vez de "Servicios" | Caché del navegador | Ctrl+Shift+R (hard refresh) |
