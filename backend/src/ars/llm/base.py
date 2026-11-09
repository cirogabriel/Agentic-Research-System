from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

from ars.llm.budget import ExecutionRecord, UsageTracker

T = TypeVar("T", bound=BaseModel)


class StructuredLLM(Protocol):

    tracker: UsageTracker

    def structured(
        self,
        schema: type[T],
        *,
        system: str,
        user: str,
        rec: ExecutionRecord | None = None,
        max_tokens: int | None = None,
        use_reserve: bool = False,
    ) -> T: ...
