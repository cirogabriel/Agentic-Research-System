
from __future__ import annotations

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

research_id_var: ContextVar[str | None] = ContextVar(
    "research_id", default=None
)

_SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{8,}"), "sk-***"),
    (re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{8,}"), r"\1***"),
    (re.compile(r"://([^:/@\s]+):[^@\s]+@"), r"://\1:***@"),
    (re.compile(r"(?i)(x-api-key['\":= ]+)[A-Za-z0-9._\-]{6,}"), r"\1***"),
]
_STANDARD = set(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {
    "message",
    "asctime",
}


def redact(text: str) -> str:
    for pattern, repl in _SECRET_PATTERNS:
        text = pattern.sub(repl, text)
    return text


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(
                timespec="milliseconds"
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        rid = research_id_var.get()
        if rid:
            payload["research_id"] = rid
        payload.update(
            {
                k: v
                for k, v in record.__dict__.items()
                if k not in _STANDARD and not k.startswith("_")
            }
        )
        if record.exc_info:
            payload["exc"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: str = "INFO", json_format: bool = True) -> None:
    handler = logging.StreamHandler(
        sys.stderr
    )  # stderr: stdout está reservado al protocolo MCP/stdio
    handler.addFilter(RedactFilter())
    handler.setFormatter(
        JsonFormatter()
        if json_format
        else logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s"
        )
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    for noisy in (
        "httpx",
        "httpcore",
        "openai",
        "urllib3",
        "sentence_transformers",
    ):
        logging.getLogger(noisy).setLevel(logging.WARNING)
