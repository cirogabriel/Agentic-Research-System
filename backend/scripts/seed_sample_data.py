from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ars.config import get_settings  # noqa: E402
from ars.db.session import session_scope  # noqa: E402
from ars.evaluation.datasets import load_dataset_file  # noqa: E402
from ars.logging_config import configure_logging  # noqa: E402
from ars.repositories.evaluation import EvaluationRepository  # noqa: E402
from ars.runtime import AppContainer  # noqa: E402


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, False)
    c = AppContainer.from_settings(
        settings, with_checkpointer=False, with_runner=False
    )
    try:
        for path in sorted((ROOT / "data" / "sample_docs").glob("*.md")):
            res = c.documents.ingest(path.name, path.read_bytes())
            print(
                f"{path.name}: {res.action} ({res.document.status}, {res.document.num_chunks} chunks)"
            )
        ds = load_dataset_file(
            ROOT / "data" / "evaluation" / "sample_retrieval_dataset.json"
        )
        with session_scope(c.session_factory) as s:
            repo = EvaluationRepository(s)
            if repo.get_dataset_by_name(ds["name"]) is None:
                created = repo.create_dataset(
                    ds["name"], ds["description"], ds["items"]
                )
                print(f"dataset '{ds['name']}' creado: {created.id}")
            else:
                print(f"dataset '{ds['name']}' ya existía")
    finally:
        c.close()


if __name__ == "__main__":
    main()
