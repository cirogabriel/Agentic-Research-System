"""Validación de archivos subidos: extensión, tamaño y firma real del contenido (no solo el nombre)."""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path

from ars.config import Settings
from ars.exceptions import FileValidationError

ALLOWED = {".pdf": "pdf", ".docx": "docx", ".txt": "txt", ".md": "md", ".markdown": "md", ".html": "html", ".htm": "html"}


def sanitize_filename(filename: str) -> str:
    name = Path(filename.replace("\\", "/")).name
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    if not name or name.startswith("."):
        raise FileValidationError("Nombre de archivo inválido")
    return name[:255]


def validate_upload(filename: str, data: bytes, settings: Settings) -> tuple[str, str]:
    """Devuelve (nombre_saneado, tipo). Lanza FileValidationError si el archivo no es aceptable."""
    name = sanitize_filename(filename)
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED:
        raise FileValidationError(f"Tipo de archivo no soportado '{ext}'. Admitidos: {', '.join(sorted(ALLOWED))}")
    if not data:
        raise FileValidationError("El archivo está vacío")
    if len(data) > settings.max_upload_bytes:
        raise FileValidationError(f"El archivo supera el límite de {settings.max_upload_mb} MB")
    kind = ALLOWED[ext]
    if kind == "pdf" and not data.startswith(b"%PDF-"):
        raise FileValidationError("El contenido no es un PDF válido")
    if kind == "docx":
        _validate_docx(data, settings)
    if kind in {"txt", "md", "html"} and b"\x00" in data[:4096]:
        raise FileValidationError("El archivo parece binario, no texto")
    return name, kind


def _validate_docx(data: bytes, settings: Settings) -> None:
    if not data.startswith(b"PK\x03\x04"):
        raise FileValidationError("El contenido no es un DOCX válido")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
            if "word/document.xml" not in names:
                raise FileValidationError("El DOCX no contiene word/document.xml")
            total = sum(i.file_size for i in zf.infolist())
            if total > settings.max_uncompressed_mb * 1024 * 1024:  # protección contra zip bombs
                raise FileValidationError("El DOCX descomprimido es demasiado grande")
    except zipfile.BadZipFile as exc:
        raise FileValidationError("El DOCX está corrupto") from exc
