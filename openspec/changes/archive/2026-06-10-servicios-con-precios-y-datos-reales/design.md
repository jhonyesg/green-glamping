# Design: Servicios con precios y datos reales

## Context

El catálogo de servicios (`offering`) se creó con la columna
`precio_cop` (Numeric) pero en el change
`ux-servicios-y-media-vinculada` interpreté mal la indicación
del usuario y quité ese campo de los templates. Además, el
catálogo está vacío en la BD — los precios solo existen en el
JSON del seed.

El dataset de Green Glamping tiene:
- `precio_general` con 6 líneas de precios hardcodeados.
- `seleccion_combo` con detalle de combos.
- 10 imágenes en `media/images/` con nombres sugerentes
  (combo-7, glamping-montana, spa-pareja, etc.).

El cambio es **correctivo + poblado de datos**: restaurar el
campo de precio en UI/API/template, y sembrar los 13 servicios
reales con sus imágenes.

## Goals / Non-Goals

**Goals:**
- Catálogo muestra precios con formato COP en todas las vistas.
- Seed inicial carga los 13 servicios con sus imágenes.
- Migración de la respuesta hardcodeada de `precio_general` a
  un template Jinja que itera `plans`.
- Limpieza de datos de prueba previos (servicios/media).

**Non-Goals:**
- Procesar pagos o señas (NO se hace; cierre comercial es
  entre el dueño y el cliente).
- Multi-imagen por servicio.
- Edición de precios en masa.

## Decisions

### Decisión 1: El campo se llama "precio_cop" y la etiqueta "Precio desde"

**Por qué:** el campo ya existe en la BD y los adapters
(`/api/plans`, contexto de template, `_build_render_context`)
ya lo referencian. Lo único que falta es la UI.

**Etiqueta "Precio desde"** en vez de "Precio": comunica al
cliente que es un punto de partida, no un precio cerrado (los
combos pueden tener extras opcionales). Es **estándar de
marketing** en muchos negocios de experiencias.

**Por qué no agregar campo "precio_hasta":** el dataset no
tiene rangos, solo precios fijos. Si en el futuro hay servicios
con rango, se agrega una columna nueva (no破坏 compatibilidad).

### Decisión 2: Catálogo con 13 servicios derivados del dataset

El dataset tiene 6 líneas en `precio_general`. Las 13 del
seed son una **expansión razonable**:

- 6 líneas originales como están (combo_glamping renombrado
  para evitar colisión con `combo_5`, que ahora es su
  propio item).
- 7 combos desglosados con nombres temáticos (Aventura
  Glamping, Aniversario, Cumpleaños, etc.). Precio $160.000
  cada uno (precio del grupo "Combos 1-7"), excepto Combo 5
  que ya tiene precio propio ($290.000).
- 2 servicios adicionales útiles: transporte (ya mencionado
  en el dataset, $60.000) y carta del restaurante (mencionado
  en varios intents, precio 0 = sin costo / incluido).

**Por qué el admin puede editar después:** los nombres y
mapeos a imágenes son una **propuesta razonable**. El dueño
del negocio los ajusta en el panel con un par de clicks.

### Decisión 3: Imágenes sembradas con key semántica

El seed actual usa key derivada del filename
(`media_001`, `media_002`, ...). Este seed usa **key
semántica** (`glamping_montana`, `spa_pareja`, etc.) para que
los servicios y el bot puedan referenciarlas directamente
sin depender del orden de subida.

Si una key ya existe (por upload manual previo), el seed la
respeta y no la duplica. Si el archivo físico cambió, se
re-hash y se reemplaza.

### Decisión 4: `precio_general` migrado a template Jinja

El intent `precio_general` tiene su `response_text` hardcodeado
con la lista de precios. Para que el catálogo vivo tome
protagonismo:

1. El seed setea `response_type='template_jinja'` y
   `response_template` con un template que itera `plans`.
2. El form de edición de intents (`/admin/kb/{id}`) muestra
   el template y permite editarlo.
3. Si el admin lo edita mal y rompe el render, el bot hace
   fallback al `response_text` hardcodeado (no se pierde).

El template propuesto (en español, con emoji):

```
💰 *Nuestros precios:*
{% for p in plans %}
• *{{ p.nombre }}* — {{ p.precio_cop | currency_cop }}
{% endfor %}
Los precios del catálogo son los mínimos posibles, no manejamos descuentos 😊
¿Cuál te interesa?
```

### Decisión 5: Limpieza de datos de prueba

El admin ya subió imágenes y creó servicios de prueba
manualmente. El seed ahora ofrece una función
`--clean` opcional que:

1. Borra servicios de prueba (`DELETE FROM offering` donde
   `source='manual' OR source='seed'` — los `seed` se vuelven
   a crear inmediatamente).
2. Borra media de prueba (`DELETE FROM media` donde
   `source='uploaded'` o key empiece con `media_00`).
3. Limpia el directorio `data/uploads/<tenant>/` de archivos
   huérfanos.

**Por qué opcional:** si el admin ya empezó a usar el
panel, no queremos borrar sus datos. El flag `--clean` se
documenta como "primera vez / reset completo".

## Risks / Trade-offs

**[R1] El nombre "Combo 1" al "Combo 7" es arbitrario**
→ El dataset solo dice "Combos 1-7" como grupo. Los nombres
temáticos (Aventura Glamping, Aniversario, etc.) son
invención. Mitigación: el admin edita fácilmente el `nombre`
de cada combo en el panel.

**[R2] Imagen vinculada puede no coincidir con el servicio**
→ El mapeo se basa en el nombre del archivo. Por ejemplo,
`combo_7_glamping-montaña-kars-44.jpg` se vincula a "Combo 1
Aventura Glamping" porque tiene "glamping-montaña" en el
nombre. La asociación es razonable pero no perfecta. Mitigación:
el admin cambia `imagen_id` en el form de edición de servicio.

**[R3] Borrar datos de prueba accidentalmente**
→ El flag `--clean` debe ser explícito. Sin el flag, el seed
es no-destructivo (idempotente, solo agrega/actualiza).

**[R4] El template de `precio_general` puede romper**
→ Si el template está mal escrito, el bot hace fallback al
`response_text` hardcodeado. Si está bien escrito, sale del
catálogo vivo. Mitigación: probar el template en el simulador
antes de publicar.

## Migration Plan

**Pre-deploy:** ninguno.

**Deploy:**
1. Merge del código.
2. Sin migración nueva: las columnas `precio_cop`,
   `response_type`, `response_template` ya existen (002 y 003).
3. Correr seed:
   ```bash
   python -m scripts.seed_green_glamping         # idempotente
   python -m scripts.seed_green_glamping --clean # reset completo
   ```
4. Verificar en `/admin/plans/?tenant=green-glamping`:
   deben aparecer 13 servicios con precios.
5. Verificar en `/admin/media/?tenant=green-glamping`:
   deben aparecer 9 imágenes (las del dataset).
6. Probar en simulador: mandar "cuánto cuesta" → la respuesta
   debe listar los 13 servicios con precios desde la BD.

**Rollback:** el seed no es destructivo sin `--clean`. Con
`--clean`, el rollback es restaurar el estado anterior desde
backup (no hay script de undo automático).

## Open Questions

1. **¿El precio de los Combos 1-7 es realmente $160.000 o
   algunos cuestan distinto?** El dueño lo aclara en el
   panel después del seed.
2. **¿Hay combos de "Pasadía" sin hospedaje?** El dataset
   menciona "planes pasadía con parapente" como categoría
   distinta. No se incluyen en este seed (queda para
   `intents-inteligentes` cuando el admin refine el catálogo).
3. **¿El admin quiere agrupar visualmente los combos?**
   (ej: una sección "Hospedaje" y otra "Pasadía"). Esto es
   scope de un editor visual de intents (próximo change).
