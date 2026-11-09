
from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from bs4 import BeautifulSoup

from ars.exceptions import ExtractionError


@dataclass
class Page:
    text: str
    number: int | None = None


@dataclass
class ExtractedDocument:
    pages: list[Page]
    title: str | None = None
    author: str | None = None
    date: datetime | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def num_pages(self) -> int | None:
        numbers = [p.number for p in self.pages if p.number is not None]
        return max(numbers) if numbers else None


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("latin-1")  # último recurso: nunca falla


def _parse_pdf_date(raw: str | None) -> datetime | None:
    # Formato PDF: D:YYYYMMDDHHmmSS...
    if not raw or not raw.startswith("D:") or len(raw) < 10:
        return None
    try:
        return datetime(
            int(raw[2:6]), int(raw[6:8]), int(raw[8:10]), tzinfo=UTC
        )
    except ValueError:
        return None


def load_pdf(data: bytes, max_pages: int) -> ExtractedDocument:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ExtractionError("El PDF está cifrado")
        if len(reader.pages) > max_pages:
            raise ExtractionError(
                f"El PDF tiene {len(reader.pages)} páginas (máximo {max_pages})"
            )
        pages = [
            Page(text=page.extract_text() or "", number=i)
            for i, page in enumerate(reader.pages, start=1)
        ]
        meta = reader.metadata
    except PdfReadError as exc:
        raise ExtractionError(f"PDF malformado: {exc}") from exc
    return ExtractedDocument(
        pages=pages,
        title=(meta.title if meta else None),
        author=(meta.author if meta else None),
        date=_parse_pdf_date(meta.get("/CreationDate") if meta else None),
    )


def load_docx(data: bytes) -> ExtractedDocument:
    from docx import Document as DocxDocument

    try:
        doc = DocxDocument(io.BytesIO(data))
    except Exception as exc:
        raise ExtractionError(f"DOCX malformado: {exc}") from exc
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            parts.append(" | ".join(c.text.strip() for c in row.cells))
    props = doc.core_properties
    created = (
        props.created.replace(tzinfo=props.created.tzinfo or UTC)
        if props.created
        else None
    )
    return ExtractedDocument(
        pages=[Page("\n".join(parts), None)],
        title=props.title or None,
        author=props.author or None,
        date=created,
    )


def load_text(data: bytes) -> ExtractedDocument:
    return ExtractedDocument(pages=[Page(_decode(data), None)])


def load_markdown(data: bytes) -> ExtractedDocument:
    text = _decode(data)
    title = None
    for line in text.splitlines(): 
        if line.startswith("# "):
            title = line[2:].strip()
            break
    return ExtractedDocument(pages=[Page(text, None)], title=title)


def load_html(data: bytes) -> ExtractedDocument:
    soup = BeautifulSoup(_decode(data), "lxml")
    for tag in soup(
        ["script", "style", "noscript", "template", "iframe"]
    ):  # nunca se conserva código ejecutable
        tag.decompose()
    title = soup.title.get_text(strip=True) if soup.title else None
    author_tag = soup.find("meta", attrs={"name": "author"})
    author = author_tag.get("content") if author_tag else None  
    text = soup.get_text(separator="\n")
    return ExtractedDocument(
        pages=[Page(text, None)],
        title=title,
        author=str(author) if author else None,
    )


def extract(
    file_type: str, data: bytes, *, max_pdf_pages: int = 500
) -> ExtractedDocument:
    if file_type == "pdf":
        return load_pdf(data, max_pdf_pages)
    if file_type == "docx":
        return load_docx(data)
    if file_type == "md":
        return load_markdown(data)
    if file_type == "html":
        return load_html(data)
    if file_type == "txt":
        return load_text(data)
    raise ExtractionError(f"Tipo no soportado: {file_type}")
