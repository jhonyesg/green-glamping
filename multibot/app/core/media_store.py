"""Media storage helpers: save uploads to disk under data/uploads/<tenant>/,
resolve serve paths, and sanitize filenames."""

import hashlib
import os
import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB

ALLOWED_MIME_PREFIXES = ("image/", "audio/")
ALLOWED_MIME_EXACT = {"application/pdf"}

ALLOWED_EXTENSIONS = {
    # images
    ".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".svg",
    # audio
    ".ogg", ".mp3", ".wav", ".m4a", ".flac", ".opus",
    # documents
    ".pdf",
}

DATA_ROOT = Path(__file__).resolve().parents[2] / "data" / "uploads"


def _tenant_dir(tenant_slug: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "", tenant_slug)
    if not safe:
        raise ValueError("tenant_slug inválido")
    d = DATA_ROOT / safe
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sanitize_filename(name: str) -> str:
    """Quita path traversal, deja solo el basename sin caracteres peligrosos."""
    base = os.path.basename(name or "file")
    base = re.sub(r"[^a-zA-Z0-9._-]", "_", base)
    if not base or base.startswith("."):
        base = "file" + (Path(base).suffix or "")
    return base[:200]


def _ext_from_mime(mime: str) -> str:
    return {
        "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
        "image/webp": ".webp", "image/gif": ".gif", "image/svg+xml": ".svg",
        "audio/ogg": ".ogg", "audio/mpeg": ".mp3", "audio/mp3": ".mp3",
        "audio/wav": ".wav", "audio/x-wav": ".wav", "audio/m4a": ".m4a",
        "audio/mp4": ".m4a", "audio/flac": ".flac", "audio/opus": ".opus",
        "application/pdf": ".pdf",
    }.get(mime.lower(), "")


def _check_allowed(mime: str) -> None:
    if not mime:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Falta MIME type")
    if mime.startswith(ALLOWED_MIME_PREFIXES) or mime in ALLOWED_MIME_EXACT:
        return
    raise HTTPException(
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail=f"Tipo de archivo no permitido: {mime}",
    )


async def save_upload(
    file: UploadFile,
    tenant_slug: str,
) -> tuple[str, str, int]:
    """
    Guarda `file` en disco bajo data/uploads/<tenant>/<sha256>.<ext>.
    Returns (relative_path, sha256, size_bytes).
    Raises HTTPException 415 si MIME no permitido, 413 si excede 50 MB.
    """
    mime = (file.content_type or "").lower()
    _check_allowed(mime)

    hasher = hashlib.sha256()
    tmp_path = _tenant_dir(tenant_slug) / f".tmp-{uuid.uuid4().hex}"

    size = 0
    with open(tmp_path, "wb") as out:
        while chunk := await file.read(1024 * 64):
            size += len(chunk)
            if size > MAX_FILE_BYTES:
                out.close()
                tmp_path.unlink(missing_ok=True)
                raise HTTPException(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Archivo excede el límite de 50 MB",
                )
            hasher.update(chunk)
            out.write(chunk)

    sha = hasher.hexdigest()
    ext = _ext_from_mime(mime) or Path(_sanitize_filename(file.filename or "")).suffix or ".bin"
    final_path = _tenant_dir(tenant_slug) / f"{sha}{ext}"
    if final_path.exists():
        tmp_path.unlink(missing_ok=True)
    else:
        tmp_path.rename(final_path)

    rel = final_path.relative_to(DATA_ROOT)
    return str(rel), sha, size


def serve_path(tenant_slug: str, filename: str) -> Path:
    """Resuelve un path de upload de forma segura. Falla si hay path traversal."""
    safe_slug = re.sub(r"[^a-zA-Z0-9_-]", "", tenant_slug)
    if not safe_slug:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="tenant_slug inválido")
    base = (DATA_ROOT / safe_slug).resolve()
    target = (base / filename).resolve()
    if not str(target).startswith(str(base)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Path inválido")
    if not target.exists() or not target.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Archivo no encontrado")
    return target


def public_url(tenant_slug: str, rel_path: str) -> str:
    return f"/media/{tenant_slug}/{rel_path}"


def tenant_uploads_dir() -> Path:
    """Para montar StaticFiles en main.py."""
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    return DATA_ROOT
