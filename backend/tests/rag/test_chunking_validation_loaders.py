import io

import pytest

from ars.config import Settings
from ars.exceptions import FileValidationError
from ars.rag.chunking import ChunkingConfig, TextChunker
from ars.rag.cleaning import clean_text
from ars.rag.loaders import Page, extract
from ars.rag.validation import sanitize_filename, validate_upload

LONG = " ".join(f"Oración número {i} sobre la tectónica de placas." for i in range(80))


@pytest.mark.parametrize("strategy", ["recursive", "fixed", "sentence"])
def test_chunk_size_is_respected_and_pages_kept(strategy):
    chunker = TextChunker(ChunkingConfig(strategy, 300, 50))
    chunks = chunker.split_pages([Page(LONG, 1), Page(LONG[:400], 2)])
    assert len(chunks) > 3
    assert all(len(c.text) <= 300 + 60 for c in chunks)  # 'sentence' puede excederse por una oración
    assert {c.page_number for c in chunks} == {1, 2}
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_overlap_repeats_text_between_consecutive_chunks():
    chunks = TextChunker(ChunkingConfig("recursive", 200, 60)).split_text(LONG)
    assert any(set(a.split()[-3:]) & set(b.split()[:12]) for a, b in zip(chunks, chunks[1:], strict=False))


def test_invalid_chunk_config():
    with pytest.raises(ValueError):
        ChunkingConfig("recursive", 200, 200)


def test_clean_text_joins_hyphenation_and_collapses_whitespace():
    assert clean_text("termi-\nnación   rápida\n\n\n\nfin\x00") == "terminación rápida\n\nfin"


def test_loaders_markdown_html_text_docx():
    md = extract("md", "# Título\n\nTexto".encode())
    assert md.title == "Título"
    html = extract("html", b"<html><head><title>T</title><meta name='author' content='Ana'><script>alert(1)</script></head><body><p>Hola</p></body></html>")
    assert html.title == "T" and html.author == "Ana" and "alert" not in html.pages[0].text and "Hola" in html.pages[0].text
    assert extract("txt", "áé".encode("latin-1")).pages[0].text == "áé"
    from docx import Document

    buf = io.BytesIO()
    d = Document()
    d.add_paragraph("Párrafo de prueba")
    d.save(buf)
    assert "Párrafo de prueba" in extract("docx", buf.getvalue()).pages[0].text


def test_validation_rejects_bad_files():
    s = Settings(_env_file=None, max_upload_mb=1)
    assert validate_upload("../../etc/a.md", b"# hola", s) == ("a.md", "md")
    for name, data in [("a.exe", b"x"), ("a.pdf", b"no es pdf"), ("a.docx", b"PK\x03\x04basura"), ("a.txt", b"\x00\x01"), ("a.txt", b""), ("a.txt", b"x" * (2 * 1024 * 1024))]:
        with pytest.raises(FileValidationError):
            validate_upload(name, data, s)
    with pytest.raises(FileValidationError):
        sanitize_filename("..")
