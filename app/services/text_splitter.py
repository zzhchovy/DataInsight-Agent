from dataclasses import dataclass

from app.core.config import get_settings
from app.services.document_loader import LoadedDocument


@dataclass(frozen=True)
class DocumentChunk:
    text: str
    source: str
    chunk_index: int
    page: int | None = None


def split_documents(documents: list[LoadedDocument]) -> list[DocumentChunk]:
    settings = get_settings()
    chunks: list[DocumentChunk] = []
    chunk_index = 0

    for document in documents:
        for text in _split_text(
            document.text,
            chunk_size=settings.chunk_size,
            overlap=settings.chunk_overlap,
        ):
            if text.strip():
                chunks.append(
                    DocumentChunk(
                        text=text.strip(),
                        source=document.source,
                        page=document.page,
                        chunk_index=chunk_index,
                    )
                )
                chunk_index += 1

    return chunks


def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not normalized:
        return []

    chunks: list[str] = []
    start = 0
    text_length = len(normalized)
    step = max(1, chunk_size - overlap)

    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunks.append(normalized[start:end])
        if end == text_length:
            break
        start += step

    return chunks

