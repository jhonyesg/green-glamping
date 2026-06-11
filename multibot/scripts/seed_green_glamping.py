"""Seed Green Glamping tenant with its KB, handoff rules, services and media.

Idempotente: corre 2 veces sin duplicar. Acepta `--clean` para
borrar datos de prueba previos antes de sembrar (reset completo).
"""

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models.plan  # noqa: F401
import app.models.tenant  # noqa: F401
from app.config import get_settings
from app.models.tenant import Tenant

SEED_FILE = Path(__file__).parent.parent / "data" / "seeds" / "green_glamping_kb.json"
CLIENT_DATA = Path(__file__).parent.parent / "data" / "clients" / "green-glamping"
SLUG = "green-glamping"

# 13 servicios del catálogo real de Green Glamping.
# Precio_cop es "precio desde" — la plataforma lo muestra pero
# no procesa pagos. El cierre comercial es entre el dueño y el cliente.
SEED_SERVICES = [
    {
        "slug": "solo_vuelo",
        "nombre": "Solo vuelo / cumple / aniversario",
        "descripcion": "Vuelo en parapente biplaza con piloto certificado. Ideal para un regalo de cumpleaños, aniversario o simplemente vivir la experiencia.",
        "precio_cop": 30000,
        "incluye": ["Vuelo parapente biplaza", "Piloto certificado", "Video del vuelo"],
        "imagen_key": None,
        "display_order": 10,
    },
    {
        "slug": "combo_glamping",
        "nombre": "Glamping + Parapente",
        "descripcion": "Una noche de Glamping Montaña con vuelo en parapente biplaza para dos personas.",
        "precio_cop": 200000,
        "incluye": ["1 noche Glamping Montaña", "Vuelo parapente biplaza para 2", "Desayuno"],
        "imagen_key": "glamping_montana",
        "display_order": 20,
    },
    {
        "slug": "combos_1_a_7_1",
        "nombre": "Combo 1 — Aventura Glamping",
        "descripcion": "Vivencia completa de aventura y descanso en la montaña.",
        "precio_cop": 160000,
        "incluye": ["Hospedaje Glamping", "Actividad de aventura a elegir"],
        "imagen_key": "combo_7_glamping",
        "display_order": 31,
    },
    {
        "slug": "combos_1_a_7_2",
        "nombre": "Combo 2 — Aniversario Romántico",
        "descripcion": "Escapada romántica para celebrar en pareja.",
        "precio_cop": 160000,
        "incluye": ["Glamping Montaña", "Cena romántica", "Decoración especial"],
        "imagen_key": "spa_pareja",
        "display_order": 32,
    },
    {
        "slug": "combos_1_a_7_3",
        "nombre": "Combo 3 — Cumpleaños Inolvidable",
        "descripcion": "Celebración de cumpleaños con decoración y experiencia.",
        "precio_cop": 160000,
        "incluye": ["Glamping", "Decoración de cumpleaños", "Cena grupal"],
        "imagen_key": "decoracion_cumpleanos",
        "display_order": 33,
    },
    {
        "slug": "combos_1_a_7_4",
        "nombre": "Combo 4 — Desconexión Total",
        "descripcion": "Para salir de la rutina y conectar con la naturaleza.",
        "precio_cop": 160000,
        "incluye": ["Glamping Montaña", "Senderismo guiado", "Comida local"],
        "imagen_key": "glamping_descripcion",
        "display_order": 34,
    },
    {
        "slug": "combos_1_a_7_5",
        "nombre": "Combo 5 — Experiencia Completa",
        "descripcion": "El combo más vendido: glamping + parapente + spa.",
        "precio_cop": 290000,
        "incluye": ["1 noche Glamping", "Vuelo parapente para 2", "Spa pareja con jacuzzi", "Cena romántica"],
        "imagen_key": "vista_glamping_montana",
        "display_order": 35,
    },
    {
        "slug": "combos_1_a_7_6",
        "nombre": "Combo 6 — Glamping + Adrenalina",
        "descripcion": "Para los que buscan acción y naturaleza juntas.",
        "precio_cop": 160000,
        "incluye": ["Glamping", "Cars 4x4 o cabalgata", "Vuelo parapente"],
        "imagen_key": "portafolio_glamping",
        "display_order": 36,
    },
    {
        "slug": "combos_1_a_7_7",
        "nombre": "Combo 7 — Glamping Premium Cristal",
        "descripcion": "Experiencia premium en el Glamping Cristal 360°.",
        "precio_cop": 160000,
        "incluye": ["1 noche Glamping Cristal", "Cena gourmet", "Spa"],
        "imagen_key": "glamping_montana",
        "display_order": 37,
    },
    {
        "slug": "parapente_individual",
        "nombre": "Parapente individual",
        "descripcion": "Vuelo en parapente biplaza para una persona.",
        "precio_cop": 220000,
        "incluye": ["Vuelo parapente biplaza", "Piloto certificado", "Video del vuelo"],
        "imagen_key": "portafolio_parapente",
        "display_order": 40,
    },
    {
        "slug": "spa_pareja",
        "nombre": "Spa pareja con jacuzzi",
        "descripcion": "Sesión de spa para dos con jacuzzi y sauna.",
        "precio_cop": 130000,
        "incluye": ["Sauna + jacuzzi para 2", "Masaje relajante", "Cena opcional"],
        "imagen_key": "spa_pareja",
        "display_order": 50,
    },
    {
        "slug": "transporte_chipaque",
        "nombre": "Transporte desde Chipaque",
        "descripcion": "Traslado desde el municipio de Chipaque hasta las instalaciones y regreso.",
        "precio_cop": 60000,
        "incluye": ["Ida y vuelta por pareja", "Desde el municipio de Chipaque"],
        "imagen_key": None,
        "display_order": 60,
    },
    {
        "slug": "carta_restaurante",
        "nombre": "Carta del restaurante",
        "descripcion": "Servicio de restaurante con variedad de bebidas y alimentos. Incluido en algunos hospedajes.",
        "precio_cop": 0,
        "incluye": ["Carta de bebidas", "Carta de alimentos", "Atención en el sitio"],
        "imagen_key": "carta_bebidas",
        "display_order": 70,
    },
]

# Mapeo de media_key (semántica) → archivo físico en el dataset.
MEDIA_KEY_TO_FILE = {
    "glamping_montana": "glamping-montana.jpg",
    "glamping_descripcion": "glamping-descripcion.jpg",
    "vista_glamping_montana": "vista-glamping-montana.jpg",
    "portafolio_glamping": "portafolio-glamping.jpg",
    "portafolio_parapente": "portafolio-parapente.jpg",
    "combo_7_glamping": "combo-7-glamping-montaña-kars-44.jpg",
    "spa_pareja": "spa-pareja.jpg",
    "decoracion_cumpleanos": "decoracion-cumpleanos.jpg",
    "carta_bebidas": "carta-bebidas.jpg",
    "medios_pago": "medios-de-pago-titular.jpg",
}


def _format_cop(value) -> str:
    try:
        n = int(float(value))
    except (TypeError, ValueError):
        return str(value)
    return f"${n:,}".replace(",", ".")


async def _ensure_schema_has_tables(session, schema: str) -> None:
    """Crea offering y media en el schema del tenant si no existen (idempotente)."""
    await session.execute(sa.text(f'CREATE SCHEMA IF NOT EXISTS "{schema}"'))
    for table, ddl in [
        ("offering", """
            CREATE TABLE IF NOT EXISTS offering (
                id SERIAL PRIMARY KEY,
                slug VARCHAR(100) NOT NULL UNIQUE,
                nombre VARCHAR(200) NOT NULL,
                descripcion TEXT,
                precio_cop NUMERIC(12,2) NOT NULL DEFAULT 0,
                incluye JSONB NOT NULL DEFAULT '[]'::jsonb,
                imagen_id INTEGER,
                display_order INTEGER NOT NULL DEFAULT 100,
                is_active BOOLEAN NOT NULL DEFAULT true,
                source VARCHAR(20) NOT NULL DEFAULT 'seed',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """),
        ("media", """
            CREATE TABLE IF NOT EXISTS media (
                id SERIAL PRIMARY KEY,
                key VARCHAR(150) NOT NULL UNIQUE,
                tipo VARCHAR(20) NOT NULL,
                path VARCHAR(500) NOT NULL,
                mime_type VARCHAR(100) NOT NULL,
                size_bytes INTEGER NOT NULL DEFAULT 0,
                original_filename VARCHAR(300),
                original_path VARCHAR(500),
                descripcion VARCHAR(500),
                uploaded_by VARCHAR(100),
                source VARCHAR(20) NOT NULL DEFAULT 'seed',
                is_active BOOLEAN NOT NULL DEFAULT true,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
        """),
    ]:
        # Reemplazar el prefijo "CREATE TABLE" del DDL para incluir el schema
        ddl_with_schema = ddl.replace("CREATE TABLE IF NOT EXISTS", f'CREATE TABLE IF NOT EXISTS "{schema}".')
        await session.execute(sa.text(ddl_with_schema))

    # Asegurar columnas de kb_intents que requieren las migraciones 003 y 004.
    # El seed debe ser autocontenido: si las migraciones no se corrieron,
    # el seed agrega las columnas con ALTER TABLE ADD COLUMN IF NOT EXISTS.
    await _ensure_kb_intent_columns(session, schema)


async def _ensure_kb_intent_columns(session, schema: str) -> None:
    """Agrega columnas de migraciones 003/004 a kb_intents si faltan."""
    # Migración 003
    await session.execute(sa.text(
        f'ALTER TABLE "{schema}".kb_intents ADD COLUMN IF NOT EXISTS '
        f'response_type VARCHAR(20) NOT NULL DEFAULT \'static\''
    ))
    await session.execute(sa.text(
        f'ALTER TABLE "{schema}".kb_intents ADD COLUMN IF NOT EXISTS '
        f'response_template TEXT'
    ))
    await session.execute(sa.text(
        f'ALTER TABLE "{schema}".kb_intents ADD COLUMN IF NOT EXISTS '
        f'requires_data JSONB'
    ))
    # Migración 004
    await session.execute(sa.text(
        f'ALTER TABLE "{schema}".kb_intents ADD COLUMN IF NOT EXISTS '
        f'response_media_ids JSONB NOT NULL DEFAULT \'[]\'::jsonb'
    ))


async def clear_demo_data(session, schema: str, tenant_slug: str) -> None:
    """
    Borra servicios de prueba y media de prueba. Usar con cuidado.
    """
    # Servicios manuales y de seed (estos últimos se recrean abajo)
    await session.execute(sa.text(
        f'DELETE FROM "{schema}".offering WHERE source IN (\'manual\', \'seed\')'
    ))
    # Media subida manualmente o autogenerada (media_00X)
    await session.execute(sa.text(
        f'DELETE FROM "{schema}".media WHERE source = \'uploaded\' OR key LIKE \'media_0%\''
    ))
    # Limpiar archivos huérfanos en disco (los que ya no tienen fila)
    from app.core.media_store import DATA_ROOT
    upload_dir = DATA_ROOT / tenant_slug
    if upload_dir.exists():
        # Consultar qué paths siguen vivos en BD
        alive_paths = set()
        rows = (await session.execute(
            sa.text(f'SELECT path FROM "{schema}".media')
        )).fetchall()
        alive_paths = {r[0] for r in rows}
        # Borrar archivos cuyo path no esté en la BD
        for f in upload_dir.iterdir():
            try:
                rel = str(f.relative_to(DATA_ROOT))
            except ValueError:
                continue
            if rel not in alive_paths:
                f.unlink(missing_ok=True)


async def seed_services(session, schema: str) -> dict:
    """
    Inserta/actualiza los servicios del SEED_SERVICES.
    Devuelve {slug: media_id} para vincular imágenes.
    """
    inserted = 0
    for s in SEED_SERVICES:
        existing = (await session.execute(
            sa.text(f'SELECT id, source FROM "{schema}".offering WHERE slug=:s'),
            {"s": s["slug"]},
        )).fetchone()
        if existing is None:
            await session.execute(
                sa.text(
                    "INSERT INTO offering (slug, nombre, descripcion, precio_cop, "
                    "incluye, display_order, is_active, source) "
                    "VALUES (:slug, :nombre, :desc, :precio, CAST(:incluye AS jsonb), "
                    ":ord, true, 'seed')"
                ),
                {
                    "slug": s["slug"], "nombre": s["nombre"],
                    "desc": s.get("descripcion"),
                    "precio": s["precio_cop"],
                    "incluye": json.dumps(s["incluye"]),
                    "ord": s["display_order"],
                },
            )
            inserted += 1
        elif existing.source != "manual":
            await session.execute(
                sa.text(
                    "UPDATE offering SET nombre=:nombre, descripcion=:desc, "
                    "precio_cop=:precio, incluye=CAST(:incluye AS jsonb), "
                    "display_order=:ord, is_active=true "
                    "WHERE slug=:slug"
                ),
                {
                    "slug": s["slug"], "nombre": s["nombre"],
                    "desc": s.get("descripcion"),
                    "precio": s["precio_cop"],
                    "incluye": json.dumps(s["incluye"]),
                    "ord": s["display_order"],
                },
            )
            inserted += 1
    return inserted


async def seed_media_with_keys(session, schema: str) -> int:
    """
    Carga imágenes del cliente con key semántica. Si la key ya
    existe, actualiza el path al archivo físico actual (idempotente).
    """
    from app.core.media_store import DATA_ROOT
    images_dir = CLIENT_DATA / "media" / "images"
    if not images_dir.exists():
        return 0

    target_dir = DATA_ROOT / SLUG
    target_dir.mkdir(parents=True, exist_ok=True)

    mime_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
        ".webp": "image/webp", ".gif": "image/gif",
    }

    # Construir índice inverso: nombre de archivo → media_key semántica
    file_to_key = {fname: key for key, fname in MEDIA_KEY_TO_FILE.items()}

    inserted = 0
    for img in sorted(images_dir.iterdir()):
        if img.suffix.lower() not in mime_map:
            continue
        mime = mime_map[img.suffix.lower()]
        # Si el archivo está mapeado a una key semántica, usarla
        # Si no, derivar del nombre (snake_case sin extensión)
        if img.name in file_to_key:
            key = file_to_key[img.name]
        else:
            key = img.stem.lower().replace("-", "_").replace(" ", "_")
        sha = hashlib.sha256(img.read_bytes()).hexdigest()
        ext = img.suffix.lower()
        target = target_dir / f"{sha}{ext}"
        if not target.exists():
            target.write_bytes(img.read_bytes())
        rel = f"{sha}{ext}"

        existing = (await session.execute(
            sa.text(f'SELECT id, path FROM "{schema}".media WHERE key=:k'),
            {"k": key},
        )).fetchone()
        if existing is None:
            await session.execute(
                sa.text(
                    "INSERT INTO media (key, tipo, path, mime_type, size_bytes, "
                    "original_filename, original_path, uploaded_by, source) "
                    "VALUES (:k, 'image', :p, :m, :s, :o, :op, 'seed', 'seed')"
                ),
                {
                    "k": key, "p": rel, "m": mime,
                    "s": img.stat().st_size,
                    "o": img.name,
                    "op": str(img.relative_to(Path(__file__).parent.parent)),
                },
            )
            inserted += 1
        elif existing.path != rel:
            # Archivo cambió (mismo nombre, contenido distinto). Actualizar.
            await session.execute(
                sa.text(
                    "UPDATE media SET path=:p, mime_type=:m, size_bytes=:s, "
                    "original_filename=:o, is_active=true WHERE key=:k"
                ),
                {"p": rel, "m": mime, "s": img.stat().st_size,
                 "o": img.name, "k": key},
            )
    return inserted


async def link_services_to_media(session, schema: str) -> int:
    """
    Resuelve imagen_key → media.id y actualiza offering.imagen_id.
    """
    # Cargar todas las media_keys del schema
    rows = (await session.execute(
        sa.text(f'SELECT key, id FROM "{schema}".media WHERE is_active=true')
    )).fetchall()
    key_to_id = {r.key: r.id for r in rows}

    updated = 0
    for s in SEED_SERVICES:
        key = s.get("imagen_key")
        if not key:
            continue
        media_id = key_to_id.get(key)
        if not media_id:
            continue
        await session.execute(
            sa.text(
                "UPDATE offering SET imagen_id=:mid WHERE slug=:s"
            ),
            {"mid": media_id, "s": s["slug"]},
        )
        updated += 1
    return updated


async def set_precio_general_template(session, schema: str) -> int:
    """
    Migra el intent `precio_general` a template Jinja que itera
    `plans` (catálogo vivo). Deja el response_text original como
    fallback.
    """
    template = (
        "💰 *Nuestros precios:*\n"
        "{% for p in plans %}"
        "• *{{ p.nombre }}* — {{ p.precio_cop | currency_cop }}\n"
        "{% endfor %}"
        "Los precios del catálogo son los mínimos posibles, no manejamos descuentos 😊\n"
        "¿Cuál te interesa?"
    )
    await session.execute(
        sa.text(
            "UPDATE kb_intents SET response_type='template_jinja', "
            "response_template=:tpl "
            "WHERE intent_name='precio_general'"
        ),
        {"tpl": template},
    )
    return 1


async def seed_kb_intents(session, schema: str, seed_data: dict, tenant_id: int) -> int:
    """Inserta/actualiza los intents de la KB (lógica del seed original)."""
    inserted = 0
    await session.execute(sa.text("DELETE FROM kb_intents WHERE source='seed'"))

    for intent in seed_data["intents"]:
        existing = (await session.execute(
            sa.text("SELECT id FROM kb_intents WHERE intent_name=:n"),
            {"n": intent["intent_name"]},
        )).fetchone()
        if existing:
            await session.execute(
                sa.text("""
                    UPDATE kb_intents SET keywords_regex=:kr, response_text=:rt,
                    handoff_rule=:hr, requires_human=:rh, human_reason=:hn, priority=:pr,
                    source='seed' WHERE intent_name=:n
                """),
                {
                    "kr": intent["keywords_regex"], "rt": intent["response_text"],
                    "hr": intent.get("handoff_rule"), "rh": intent.get("requires_human", False),
                    "hn": intent.get("human_reason"), "pr": intent.get("priority", 5),
                    "n": intent["intent_name"],
                },
            )
        else:
            await session.execute(
                sa.text("""
                    INSERT INTO kb_intents
                    (tenant_id, intent_name, keywords_regex, response_text,
                     handoff_rule, requires_human, human_reason, priority, status, source)
                    VALUES (:tenant_id, :intent_name, :keywords_regex, :response_text,
                            :handoff_rule, :requires_human, :human_reason, :priority,
                            'active', 'seed')
                """),
                {
                    "tenant_id": tenant_id,
                    "intent_name": intent["intent_name"],
                    "keywords_regex": intent["keywords_regex"],
                    "response_text": intent["response_text"],
                    "handoff_rule": intent.get("handoff_rule"),
                    "requires_human": intent.get("requires_human", False),
                    "human_reason": intent.get("human_reason"),
                    "priority": intent.get("priority", 5),
                },
            )
        inserted += 1
    return inserted


async def seed_handoff_rules(session, schema: str, seed_data: dict, tenant_id: int) -> int:
    """Inserta/actualiza las handoff rules."""
    inserted = 0
    await session.execute(sa.text("DELETE FROM handoff_rules WHERE is_active=true"))
    for rule in seed_data["handoff_rules"]:
        await session.execute(
            sa.text("""
                INSERT INTO handoff_rules
                (tenant_id, mode, rule_code, trigger_intent,
                 notify_channel, notify_target, custom_message,
                 is_active, priority)
                VALUES (:tenant_id, :mode, :rule_code, :trigger_intent,
                        :notify_channel, :notify_target, :custom_message,
                        :is_active, :priority)
            """),
            {
                "tenant_id": tenant_id,
                "mode": rule["mode"],
                "rule_code": rule["rule_code"],
                "trigger_intent": rule["trigger_intent"],
                "notify_channel": rule["notify_channel"],
                "notify_target": rule["notify_target"],
                "custom_message": rule["custom_message"],
                "is_active": rule["is_active"],
                "priority": rule["priority"],
            },
        )
        inserted += 1
    return inserted


async def seed(clean: bool = False):
    settings = get_settings()
    engine = create_async_engine(settings.get_database_url(), echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    seed_data = json.loads(SEED_FILE.read_text())
    schema = f"tenant_{SLUG}"

    async with session_factory() as session:
        existing = (await session.execute(
            sa.select(Tenant).where(Tenant.slug == SLUG)
        )).scalar_one_or_none()

        if existing is None:
            await engine.dispose()
            print(f"Tenant '{SLUG}' not found. Running create_tenant first...")
            subprocess.run(
                [sys.executable, "-m", "scripts.create_tenant",
                 "--slug", SLUG,
                 "--name", seed_data["tenant_name"],
                 "--mode", seed_data["operation_mode"]],
                check=True,
            )
            engine = create_async_engine(settings.get_database_url(), echo=False)
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session2:
                tenant = (await session2.execute(
                    sa.select(Tenant).where(Tenant.slug == SLUG)
                )).scalar_one()
                tenant_id = tenant.id
        else:
            tenant_id = existing.id
            print(f"Tenant '{SLUG}' already exists (ID={tenant_id})")

    # Asegurar schema con tablas
    async with session_factory() as session:
        await _ensure_schema_has_tables(session, schema)
        await session.commit()
    print(f"✓ Schema '{schema}' con tablas offering y media asegurado")

    # Limpiar datos de prueba si se pidió
    if clean:
        async with session_factory() as session:
            await clear_demo_data(session, schema, SLUG)
            await session.commit()
        print("✓ Datos de prueba borrados (--clean)")

    # Sembrar todo
    async with session_factory() as session:
        await session.execute(sa.text(f'SET search_path TO "{schema}", public'))

        intents = await seed_kb_intents(session, schema, seed_data, tenant_id)
        handoffs = await seed_handoff_rules(session, schema, seed_data, tenant_id)
        services = await seed_services(session, schema)
        media = await seed_media_with_keys(session, schema)
        linked = await link_services_to_media(session, schema)
        precio_migrated = await set_precio_general_template(session, schema)

        await session.commit()
        print(
            f"✓ Sembrado: {intents} intents, {handoffs} handoff rules, "
            f"{services} servicios, {media} media, {linked} servicios con imagen vinculada, "
            f"{precio_migrated} intent migrado a template"
        )

    await engine.dispose()
    print("✓ Green Glamping listo para producción.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--clean", action="store_true",
        help="Borra servicios/media de prueba antes de sembrar (reset completo).",
    )
    args = parser.parse_args()
    asyncio.run(seed(clean=args.clean))
