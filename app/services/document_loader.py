from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


SUPPORTED_DOCUMENT_EXTENSIONS = {".txt", ".md", ".markdown", ".pdf"}


@dataclass(frozen=True)
class LoadedDocument:
    text: str
    source: str
    page: int | None = None


def load_document(path: Path, source_name: str | None = None) -> list[LoadedDocument]:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_DOCUMENT_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_DOCUMENT_EXTENSIONS))
        raise ValueError(f"Unsupported document type: {suffix}. Supported: {supported}")

    if suffix == ".pdf":
        return _load_pdf(path, source_name=source_name)

    text = path.read_text(encoding="utf-8")
    return [LoadedDocument(text=text, source=source_name or path.name)]


def _load_pdf(path: Path, source_name: str | None = None) -> list[LoadedDocument]:
    reader = PdfReader(str(path))
    documents: list[LoadedDocument] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            documents.append(
                LoadedDocument(text=text, source=source_name or path.name, page=page_number)
            )
    return documents
