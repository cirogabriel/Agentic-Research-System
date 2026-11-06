from __future__ import annotations

import re
import unicodedata

CLEANING_VERSION = "1"  # forma parte de la firma de indexación: cambiarla fuerza reindexar

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HYPHEN_BREAK = re.compile(r"(\w)-\n(\w)")
_SPACES = re.compile(r"[ \t\u00a0]+")
_BLANKS = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    """Normaliza Unicode, elimina caracteres de control, une palabras cortadas por guion y compacta espacios."""
    text = unicodedata.normalize("NFKC", text)
    text = _CONTROL.sub("", text)
    text = _HYPHEN_BREAK.sub(r"\1\2", text)
    text = _SPACES.sub(" ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    return _BLANKS.sub("\n\n", text).strip()
