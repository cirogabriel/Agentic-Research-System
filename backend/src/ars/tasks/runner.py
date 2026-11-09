

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

log = logging.getLogger(__name__)


class BackgroundRunner:
    def __init__(self, max_workers: int) -> None:
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="ars-job"
        )

    def submit(
        self, fn: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Future[Any]:
        def wrapped() -> Any:
            try:
                return fn(*args, **kwargs)
            except Exception:
                log.exception(
                    "Error no controlado en tarea de segundo plano",
                    extra={"job": getattr(fn, "__name__", str(fn))},
                )
                raise

        return self._pool.submit(wrapped)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)


class InlineRunner:

    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        fn(*args, **kwargs)

    def shutdown(self) -> None:
        pass
