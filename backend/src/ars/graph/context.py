from __future__ import annotations

from langchain_core.messages import (
    AnyMessage,
    RemoveMessage,
    filter_messages,
    trim_messages,
)
from langchain_core.messages.utils import count_tokens_approximately


def build_notes(
    messages: list[AnyMessage], names: set[str], max_tokens: int
) -> str:
    selected = filter_messages(messages, include_names=sorted(names))
    trimmed = trim_messages(
        selected,
        max_tokens=max_tokens,
        strategy="last",
        token_counter=count_tokens_approximately,
        allow_partial=False,
    )
    return "\n".join(f"[{m.name}] {m.content}" for m in trimmed)


def prune_messages(
    messages: list[AnyMessage], keep_last: int
) -> list[RemoveMessage]:
    old = messages[:-keep_last] if keep_last > 0 else list(messages)
    return [RemoveMessage(id=m.id) for m in old if m.id]
