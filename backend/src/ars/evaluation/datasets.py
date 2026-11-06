from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ars.schemas.api import EvalItem


def load_dataset_file(path: str | Path) -> dict[str, Any]:
    """Carga y valida un dataset JSON: {name, description, items:[EvalItem]}."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    items = [EvalItem(**i).model_dump() for i in raw["items"]]
    ids = [i["id"] for i in items]
    if len(ids) != len(set(ids)):
        raise ValueError("Los ids de los ítems del dataset deben ser únicos")
    return {"name": raw["name"], "description": raw.get("description"), "items": items}
