"""Estrategias de chunking configurables (tamaño, solapamiento, separadores, estrategia)."""
from __future__ import annotations

from dataclasses import dataclass

from langchain_text_splitters import CharacterTextSplitter, RecursiveCharacterTextSplitter

from ars.config import Settings
from ars.rag.loaders import Page
from ars.utils.text import approx_tokens, split_sentences


@dataclass(frozen=True)
class ChunkingConfig:
    strategy: str = "recursive"  # recursive | fixed | sentence
    size: int = 1000
    overlap: int = 150
    separators: tuple[str, ...] = ("\n\n", "\n", ". ", " ", "")

    def __post_init__(self) -> None:
        if self.size < 100:
            raise ValueError("chunk_size debe ser >= 100")
        if not 0 <= self.overlap < self.size:
            raise ValueError("chunk_overlap debe estar en [0, chunk_size)")

    @classmethod
    def from_settings(cls, s: Settings) -> ChunkingConfig:
        return cls(s.chunk_strategy, s.chunk_size, s.chunk_overlap, tuple(s.chunk_separators))


@dataclass
class Chunk:
    index: int
    text: str
    page_number: int | None
    token_estimate: int


class TextChunker:
    def __init__(self, config: ChunkingConfig) -> None:
        self.config = config
        if config.strategy == "recursive":
            self._splitter = RecursiveCharacterTextSplitter(
                chunk_size=config.size, chunk_overlap=config.overlap, separators=list(config.separators), length_function=len
            )
        elif config.strategy == "fixed":
            self._splitter = CharacterTextSplitter(separator="", chunk_size=config.size, chunk_overlap=config.overlap, length_function=len)
        elif config.strategy == "sentence":
            self._splitter = None
        else:
            raise ValueError(f"Estrategia de chunking desconocida: {config.strategy}")

    def split_text(self, text: str) -> list[str]:
        if self._splitter is not None:
            return [c.strip() for c in self._splitter.split_text(text) if c.strip()]
        return self._split_sentences(text)

    def _split_sentences(self, text: str) -> list[str]:
        """Empaqueta oraciones completas hasta `size`; el solapamiento reutiliza las últimas oraciones."""
        chunks: list[str] = []
        current: list[str] = []
        length = 0
        for sentence in split_sentences(text):
            if current and length + len(sentence) + 1 > self.config.size:
                chunks.append(" ".join(current))
                carry: list[str] = []
                carried = 0
                for prev in reversed(current):
                    if carried + len(prev) > self.config.overlap:
                        break
                    carry.insert(0, prev)
                    carried += len(prev) + 1
                current, length = carry, carried
            current.append(sentence)
            length += len(sentence) + 1
        if current:
            chunks.append(" ".join(current))
        return chunks

    def split_pages(self, pages: list[Page]) -> list[Chunk]:
        """Se divide página a página para conservar el número de página en cada chunk."""
        out: list[Chunk] = []
        for page in pages:
            for piece in self.split_text(page.text):
                out.append(Chunk(index=len(out), text=piece, page_number=page.number, token_estimate=approx_tokens(piece)))
        return out
