"""Caché en memoria con TTL y límite de tamaño (LRU simple), segura entre hilos."""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Generic, TypeVar

V = TypeVar("V")


class TTLCache(Generic[V]):
    def __init__(self, max_size: int, ttl_seconds: float) -> None:
        self.max_size, self.ttl = max_size, ttl_seconds
        self._data: OrderedDict[str, tuple[float, V]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str) -> V | None:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            ts, value = item
            if self.ttl > 0 and time.monotonic() - ts > self.ttl:
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key: str, value: V) -> None:
        if self.max_size <= 0 or self.ttl <= 0:
            return
        with self._lock:
            self._data[key] = (time.monotonic(), value)
            self._data.move_to_end(key)
            while len(self._data) > self.max_size:
                self._data.popitem(last=False)

    def clear(self) -> None:
        """Se llama al indexar/eliminar documentos: los resultados cacheados dejarían de ser válidos."""
        with self._lock:
            self._data.clear()
