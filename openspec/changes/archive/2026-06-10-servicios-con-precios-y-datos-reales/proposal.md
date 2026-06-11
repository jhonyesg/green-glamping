# Proposal: Servicios con precios y datos reales

## Why

En el change anterior (`ux-servicios-y-media-vinculada`) interpreté
mal la indicación: removí el campo `precio_cop` del catálogo
interpretando que "la plataforma no maneja precios". El dueño del
negocio me corrigió: **los precios sí van en el catálogo de
Servicios**, como referencia informativa para el cliente (igual
que un menú de restaurante muestra precios pero el pago se hace
en la caja). La plataforma muestra los precios pero no procesa
pagos — el cierre comercial es entre el dueño y el cliente.

Además, el catálogo está vacío en BD. Hay que poblarlo con los
datos reales del dataset de Green Glamping que están en
`multibot/data/clients/green-glamping/knowledge_base/knowledge_base.json`,
vincular las imágenes que ya existen en
`multibot/data/clients/green-glamping/media/images/`, y restaurar
el campo `precio_cop` en el form, el listado, la API y el
template de respuesta del bot.

## What Changes

- **Restaurar campo `precio_cop`** en el form de creación/edición
  de servicios. El campo es **obligatorio** (precio 0 está
  permitido para servicios sin costo como "Tour de cortesía").
- **Mostrar precio en el listado** con formato COP
  (`$30.000`, `$200.000`, etc.).
- **Incluir precio en `/api/plans`** (JSON) y en el contexto
  del template Jinja (`servicio.precio_cop`).
- **Seed inicial completo** con los 13 servicios reales del
  catálogo de Green Glamping, vinculados a las imágenes
  correspondientes.
- **Borrar las imágenes previas** que se subieron como prueba
  (key `carta_bebidas` y similares con `source='uploaded'`).
- **Borrar servicios previos** que se crearon como prueba
  (source='manual' o cualquier `media_00X`).
- **Marcar el `precio_general` intent** con
  `response_type='template_jinja'` y un template que itera
  `plans` (para que la respuesta "cuánto cuesta" use la BD en
  vez de texto hardcodeado).

## Capabilities

### New Capabilities

_Ninguna._ Este change **corrige** el cambio anterior
`ux-servicios-y-media-vinculada` y agrega datos. No introduce
nuevos capabilities.

### Modified Capabilities

- `services-ux-rename` (cambio anterior): el form de servicios
  **vuelve a mostrar el campo precio** con etiqueta clara
  ("Precio desde" para enfatizar que es referencial). El
  catálogo de servicios **muestra precios** en el listado, en
  la API, y en el template de respuesta.

## Impact

- `app/admin/templates/plans/index.html`: agregar columna
  "Precio" con formato COP, mostrar precio en form de crear.
- `app/admin/templates/plans/edit.html`: agregar campo
  `precio_cop` en el form principal.
- `app/admin/routes/plans.py`: aceptar `precio_cop: float` en
  POST crear/editar (ya estaba implementado, solo restaurado
  en el form).
- `app/admin/templates/media/index.html`: ya restaurado en
  cambio anterior, no requiere cambios.
- `app/core/template_render.py`: ya tiene filtro `currency_cop`,
  no requiere cambios.
- `app/bot/pipeline.py`: `_build_render_context` ya incluye
  `precio_cop` en cada plan, no requiere cambios.
- `scripts/seed_green_glamping.py`: reescribir `SEED_PLANS` con
  los 13 servicios reales, agregar función `clear_demo_data()`
  que borra los servicios/media previos de prueba, vincular
  cada servicio a su imagen correspondiente.
- `multibot/data/clients/green-glamping/knowledge_base/knowledge_base.json`:
  actualizar el `response_text` del intent `precio_general` para
  referenciar el catálogo vivo (esto es opcional; el
  `response_template` se setea en la BD al correr el seed).
- `docs/plans.md`: actualizar la sección de catálogo con
  referencia al precio y al hecho de que es informativo (no
  transaccional). Re-estructurar la nota de "no procesa pagos"
  para que sea clara pero no en posición dominante.

## Catálogo sembrado (13 servicios)

| Slug | Nombre | Precio (COP) | Imagen vinculada |
|---|---|---|---|
| `solo_vuelo` | Solo vuelo / cumple / aniversario | 30.000 | (sin imagen específica) |
| `combo_glamping` | Glamping + Parapente | 200.000 | `glamping_montana` |
| `combos_1_a_7_1` | Combo 1 — Aventura Glamping | 160.000 | `combo_7_glamping` |
| `combos_1_a_7_2` | Combo 2 — Aniversario Romántico | 160.000 | `spa_pareja` |
| `combos_1_a_7_3` | Combo 3 — Cumpleaños Inolvidable | 160.000 | `decoracion_cumpleanos` |
| `combos_1_a_7_4` | Combo 4 — Desconexión Total | 160.000 | `glamping_descripcion` |
| `combos_1_a_7_5` | Combo 5 — Experiencia Completa | 290.000 | `vista_glamping_montana` |
| `combos_1_a_7_6` | Combo 6 — Glamping + Adrenalina | 160.000 | `portafolio_glamping` |
| `combos_1_a_7_7` | Combo 7 — Glamping Premium Cristal | 160.000 | `glamping_montana` |
| `parapente_individual` | Parapente individual | 220.000 | `portafolio_parapente` |
| `spa_pareja` | Spa pareja con jacuzzi | 130.000 | `spa_pareja` |
| `transporte_chipaque` | Transporte desde Chipaque | 60.000 | (sin imagen específica) |
| `carta_restaurante` | Carta del restaurante | 0 | `carta_bebidas` |

> Los nombres y mapeos a imágenes son una **propuesta
> razonable** basada en los nombres de archivo. El dueño del
> negocio los ajusta en el panel después de ver el resultado.

## Out of scope (cambios futuros)

- Reservas reales integradas al calendario (cambio
  `reservation-lifecycle` existente, requiere integración con
  Google Calendar).
- Sistema de seña/abono en la plataforma (NO se hace: el
  dueño cobra por fuera).
- Sincronización con un POS o sistema de caja externo.
- Galería multi-imagen por servicio.
