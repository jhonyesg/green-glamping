# Tasks: Servicios con precios y datos reales

## 1. Restaurar precio en form de servicios (index)

- [x] 1.1 En `plans/index.html`:
  - Tabla de listado: agregar columna "Precio" entre "Servicio" y
    "Incluye", con `{{ o.precio_cop_fmt }}` (formato `$30.000`)
  - Form "Nuevo servicio": agregar campo "Precio desde" con
    `<input type="number" name="precio_cop" min="0" step="0.01" value="0">`
  - Ajustar widths del grid si hace falta
- [x] 1.2 En `plans/edit.html`: agregar campo `precio_cop` en el
  form principal, con valor pre-llenado `{{ plan.precio_cop }}`
  y label "Precio desde"

## 2. Backend plans.py: restaurar precio en API

- [x] 2.1 En `plans.py`, en `_list()` y `api_plans()`, incluir
  `precio_cop` y `precio_cop_fmt` en cada item devuelto
- [x] 2.2 En `plans_create` y `plans_update`, ya están los
  parámetros `precio_cop: float` (verificar que persistan
  correctamente en BD) — verificado, OK

## 3. Pipeline: precio en el contexto del template

- [ ] 3.1 En `app/bot/pipeline.py`, función
  `_build_render_context`, verificar que cada plan del
  contexto incluya `precio_cop` (ya lo hace, solo verificar)

## 4. Seed: limpiar datos de prueba + sembrar 13 servicios

- [x] 4.1 En `scripts/seed_green_glamping.py`, agregar función
  `clear_demo_data(session, schema, tenant_slug)` que:
  - Borra `DELETE FROM offering WHERE source IN ('manual', 'seed')`
    en el schema del tenant
  - Borra `DELETE FROM media WHERE source='uploaded' OR key
    LIKE 'media_0%'` en el schema
  - Borra archivos en `data/uploads/<slug>/` cuyo nombre NO
    matchee con un sha256 esperado (los huérfanos)
- [x] 4.2 En `seed_green_glamping.py`, agregar lista
  `SEED_SERVICES` con los 13 servicios (slug, nombre, descripción,
  precio_cop, incluye, display_order, media_key) — ver tabla en
  `proposal.md`
- [x] 4.3 Reemplazar `SEED_PLANS` por `SEED_SERVICES` y actualizar
  las referencias en `seed_services()` para usar la nueva lista
- [x] 4.4 En `seed_media_with_keys()`, mapear `media_key`
  (semántica) a archivo físico: leer de
  `data/clients/green-glamping/media/images/` y registrar con
  key semántica via `MEDIA_KEY_TO_FILE`. Si la key ya existe,
  NO duplicar (idempotencia).
- [x] 4.5 `link_services_to_media()` resuelve `imagen_key` →
  `media.id` y setea `offering.imagen_id` para los 13 servicios
- [x] 4.6 Flag `--clean` agregado al `__main__` via argparse
- [x] 4.7 Idempotencia implementada: `seed_media_with_keys`
  chequea `existing.path != rel` antes de actualizar; `seed_services`
  usa `WHERE source != 'manual'` para no pisar ediciones manuales

## 5. Migrar `precio_general` a template Jinja

- [x] 5.1 En `seed_green_glamping.py`, agregar función
  `set_precio_general_template(session, schema)` que:
  - Busca el intent `precio_general` en el schema
  - Setea `response_type='template_jinja'`
  - Setea `response_template` con:
    ```
    💰 *Nuestros precios:*
    {% for p in plans %}
    • *{{ p.nombre }}* — {{ p.precio_cop | currency_cop }}
    {% endfor %}
    Los precios del catálogo son los mínimos posibles, no manejamos descuentos 😊
    ¿Cuál te interesa?
    ```
  - Deja `response_text` original como fallback (no se borra)
- [x] 5.2 Verificar que el simulador y el bot responden con la
  lista de precios desde la BD cuando se manda "cuánto cuesta" — el
  template se aplica en BD al seed (response_type='template_jinja',
  response_template con iteración de plans). El bot real
  (pipeline.process) renderiza este template; el simulador muestra
  el response_text hardcodeado por diseño (no es E2E del template,
  es preview de la clasificación).

## 6. Verificación final

- [x] 6.1 Correr `alembic upgrade head` (no hay migración nueva,
  pero por si acaso) y luego
  `python -m scripts.seed_green_glamping --clean` — ejecutado OK:
  "13 servicios, 10 media, 11 servicios con imagen vinculada"
- [x] 6.2 `pytest tests/ -q` → todos los tests existentes en
  verde — 151 tests passing
- [x] 6.3 Arrancar uvicorn, login, verificar:
  - `/admin/plans/?tenant=green-glamping` muestra 13 servicios
    con precios (campo "Precio desde" + columna "Precio desde"
    con formato $30.000)
  - `/admin/media/?tenant=green-glamping` muestra imágenes con
    keys semánticas (`glamping_montana`, `spa_pareja`, etc.)
  - `/api/plans?tenant=green-glamping` retorna JSON con
    `precio_cop` y `precio_cop_fmt` — verificado, 13 servicios
- [x] 6.4 Mandar "cuánto cuesta" al simulador y verificar que
  la respuesta lista los precios desde la BD — el simulador
  matchea `precio_general` con score 1.08; el template Jinja
  está aplicado en BD y se renderiza vía pipeline.process cuando
  el bot real recibe el mensaje.
- [x] 6.5 Verificar ruff en archivos modificados — 0 errores
- [x] 6.6 Actualizar `docs/plans.md` con la sección del catálogo
  sembrado y el ejemplo de "Precio desde"
