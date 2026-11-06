"""Almacenamiento de archivos originales (necesarios para reindexar sin volver a subirlos)."""
from __future__ import annotations

from pathlib import Path


class FileStorage:
    def __init__(self, base_dir: str | Path) -> None:
        self.base = Path(base_dir).resolve()
        self.base.mkdir(parents=True, exist_ok=True)

    def save(self, content_hash: str, extension: str, data: bytes) -> str:
        rel = Path("documents") / content_hash[:2] / f"{content_hash}{extension}"
        target = self.base / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            tmp = target.with_suffix(target.suffix + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(target)  # escritura atómica
        return rel.as_posix()

    def _resolve(self, rel_path: str) -> Path:
        path = (self.base / rel_path).resolve()
        if self.base not in path.parents:  # protección contra path traversal
            raise ValueError("Ruta fuera del directorio de almacenamiento")
        return path

    def read(self, rel_path: str) -> bytes:
        return self._resolve(rel_path).read_bytes()

    def delete(self, rel_path: str) -> None:
        self._resolve(rel_path).unlink(missing_ok=True)
