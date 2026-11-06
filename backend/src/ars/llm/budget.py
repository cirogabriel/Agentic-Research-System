"""Contabilidad de tokens y presupuesto por investigación."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from ars.config import Settings
from ars.exceptions import BudgetExceededError


@dataclass
class ExecutionRecord:
    """Lo que hizo un agente en una ejecución (tokens, herramientas, error). Se persiste como AgentExecution."""

    agent: str
    task_key: str | None = None
    iteration: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    llm_calls: int = 0
    tool_calls: list[str] = field(default_factory=list)
    error: str | None = None
    started: float = field(default_factory=time.perf_counter)

    @property
    def latency_ms(self) -> int:
        return int((time.perf_counter() - self.started) * 1000)


@dataclass
class UsageTracker:
    """Contador compartido por todas las llamadas de UNA investigación (seguro entre hilos).

    Se reserva una fracción del presupuesto (`report_reserve_ratio`) para que, aunque la investigación
    consuma casi todo, todavía se pueda redactar el informe final.
    """

    token_budget: int
    report_reserve_ratio: float = 0.2
    price_in: float = 0.15
    price_out: float = 0.60
    price_embed: float = 0.02
    tokens_in: int = 0
    tokens_out: int = 0
    embedding_tokens: int = 0
    llm_calls: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    @classmethod
    def from_settings(cls, settings: Settings, token_budget: int | None = None) -> UsageTracker:
        return cls(
            token_budget=token_budget or settings.token_budget,
            report_reserve_ratio=settings.report_reserve_ratio,
            price_in=settings.llm_price_input_per_mtok,
            price_out=settings.llm_price_output_per_mtok,
            price_embed=settings.embedding_price_per_mtok,
        )

    def charge(self, tokens_in: int, tokens_out: int) -> None:
        with self._lock:
            self.tokens_in += tokens_in
            self.tokens_out += tokens_out
            self.llm_calls += 1

    def charge_embedding(self, tokens: int) -> None:
        with self._lock:
            self.embedding_tokens += tokens

    @property
    def total(self) -> int:
        return self.tokens_in + self.tokens_out

    @property
    def remaining(self) -> int:
        return max(0, self.token_budget - self.total)

    @property
    def work_remaining(self) -> int:
        """Tokens disponibles para trabajo normal (sin tocar la reserva del informe)."""
        return max(0, int(self.token_budget * (1 - self.report_reserve_ratio)) - self.total)

    def check(self, *, use_reserve: bool = False) -> None:
        limit_left = self.remaining if use_reserve else self.work_remaining
        if limit_left <= 0:
            raise BudgetExceededError(f"Presupuesto de tokens agotado ({self.total}/{self.token_budget})")

    @property
    def cost_usd(self) -> float:
        return round(
            (self.tokens_in * self.price_in + self.tokens_out * self.price_out + self.embedding_tokens * self.price_embed) / 1_000_000, 6
        )

    def restore(self, tokens_in: int, tokens_out: int, embedding_tokens: int = 0) -> None:
        """Reanudación: se parte del consumo ya registrado en la investigación."""
        with self._lock:
            self.tokens_in, self.tokens_out, self.embedding_tokens = tokens_in, tokens_out, embedding_tokens

    def snapshot(self) -> dict[str, Any]:
        return {
            "tokens_input": self.tokens_in,
            "tokens_output": self.tokens_out,
            "embedding_tokens": self.embedding_tokens,
            "llm_calls": self.llm_calls,
            "cost_usd": self.cost_usd,
            "token_budget": self.token_budget,
        }
