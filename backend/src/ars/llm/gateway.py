"""Único punto de salida hacia el LLM generativo: salidas estructuradas, presupuesto y registro de tokens."""
from __future__ import annotations

import logging
import threading
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from ars.config import Settings
from ars.exceptions import BudgetExceededError, LLMError
from ars.llm.base import T
from ars.llm.budget import ExecutionRecord, UsageTracker
from ars.utils.text import approx_tokens

log = logging.getLogger(__name__)


class LLMGateway:
    """Todos los agentes comparten este gateway y, por tanto, el mismo modelo (LLM_MODEL)."""

    def __init__(self, settings: Settings, tracker: UsageTracker, chat_model: Any | None = None) -> None:
        self.settings = settings
        self.tracker = tracker
        self._injected = chat_model
        self._models: dict[int, Any] = {}
        self._runnables: dict[tuple[type, int], Any] = {}
        self._lock = threading.Lock()

    def _model(self, max_tokens: int) -> Any:
        if self._injected is not None:
            return self._injected
        if max_tokens not in self._models:
            s = self.settings
            self._models[max_tokens] = ChatOpenAI(
                model=s.llm_model,
                api_key=s.openai_api_key.get_secret_value() or None,
                base_url=s.openai_base_url or None,
                temperature=s.llm_temperature,
                max_tokens=max_tokens,
                timeout=s.llm_timeout_seconds,
                max_retries=s.llm_max_retries,
            )
        return self._models[max_tokens]

    def _runnable(self, schema: type[T], max_tokens: int) -> Any:
        key = (schema, max_tokens)
        with self._lock:
            if key not in self._runnables:
                # function_calling: admite valores por defecto en los esquemas Pydantic (a diferencia del modo estricto).
                self._runnables[key] = self._model(max_tokens).with_structured_output(
                    schema, method="function_calling", include_raw=True
                )
            return self._runnables[key]

    def structured(
        self,
        schema: type[T],
        *,
        system: str,
        user: str,
        rec: ExecutionRecord | None = None,
        max_tokens: int | None = None,
        use_reserve: bool = False,
    ) -> T:
        self.tracker.check(use_reserve=use_reserve)  # BudgetExceededError antes de gastar
        runnable = self._runnable(schema, max_tokens or self.settings.llm_max_output_tokens)
        messages = [SystemMessage(content=system), HumanMessage(content=user)]
        last_error = "sin detalle"
        for attempt in (1, 2):  # un único reintento si la salida no cumple el esquema
            try:
                out = runnable.invoke(messages)
            except BudgetExceededError:
                raise
            except Exception as exc:  # errores de red/API ya reintentados por el cliente OpenAI
                raise LLMError(f"Fallo al llamar al LLM: {type(exc).__name__}: {exc}") from exc
            raw = out.get("raw")
            usage = getattr(raw, "usage_metadata", None) or {}
            tin = int(usage.get("input_tokens") or approx_tokens(system + user))
            tout = int(usage.get("output_tokens") or approx_tokens(str(getattr(raw, "content", ""))))
            self.tracker.charge(tin, tout)
            if rec is not None:
                rec.tokens_in += tin
                rec.tokens_out += tout
                rec.llm_calls += 1
            parsed = out.get("parsed")
            if parsed is not None:
                return parsed  # type: ignore[no-any-return]
            last_error = str(out.get("parsing_error"))
            log.warning("Salida estructurada inválida (intento %s): %s", attempt, last_error[:200])
            if attempt == 1:
                self.tracker.check(use_reserve=use_reserve)
        raise LLMError(f"El modelo no devolvió una salida válida para {schema.__name__}: {last_error[:200]}")
