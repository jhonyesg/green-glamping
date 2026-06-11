"""Helper para auto-generar la key de un nuevo media.

La key sigue el formato `media_NNN` (1-padded). Se calcula como
MAX(existente) + 1, no como "siguiente libre": los gaps no se
reusan. Esto evita colisiones cuando el admin borra archivos.
"""

import re

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

_MEDIA_KEY_PATTERN = re.compile(r"^media_(\d+)$")


def parse_media_index(key: str) -> int | None:
    """Devuelve el N si la key matchea `media_NNN`, sino None."""
    m = _MEDIA_KEY_PATTERN.match(key or "")
    return int(m.group(1)) if m else None


async def next_media_key(tenant_slug: str, session: AsyncSession) -> str:
    """
    Devuelve la siguiente key `media_NNN` disponible para el tenant.
    MAX(existente) + 1, con padding a 3 dígitos. Si no hay ninguna,
    empieza en `media_001`.
    """
    schema = f"tenant_{tenant_slug}"
    await session.execute(sa.text(f'SET search_path TO "{schema}", public'))
    try:
        rows = (await session.execute(
            sa.text("SELECT key FROM media WHERE key LIKE 'media_%'")
        )).fetchall()
    except Exception:
        rows = []

    max_idx = 0
    for (k,) in rows:
        idx = parse_media_index(k)
        if idx is not None and idx > max_idx:
            max_idx = idx

    return f"media_{max_idx + 1:03d}"
