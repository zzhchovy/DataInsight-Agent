from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import math
import re
import uuid

from app.core.config import get_settings
from app.core.paths import vector_db_dir
from app.services.text_splitter import DocumentChunk


EMBEDDING_DIMENSION = 384


@dataclass(frozen=True)
class RetrievalHit:
    text: str
    source: str
    chunk_index: int | None
    page: int | None
    score: float | None


class VectorStore:
    """Vector store facade.

    It uses Chroma when installed. If Chroma is unavailable, it falls back to a
    tiny JSONL store so the MVP can still run in a lightweight environment.
    """

    def __init__(self, persist_dir: Path | None = None, collection_name: str | None = None):
        settings = get_settings()
        self.persist_dir = persist_dir or vector_db_dir()
        self.collection_name = collection_name or settings.vector_collection
        self._backend = _build_backend(
            persist_dir=self.persist_dir,
            collection_name=self.collection_name,
        )

    def add_chunks(self, chunks: list[DocumentChunk]) -> int:
        return self._backend.add_chunks(chunks)

    def delete_source(self, source: str) -> int:
        return self._backend.delete_source(source)

    def query(self, question: str, top_k: int = 4) -> list[RetrievalHit]:
        return self._backend.query(question, top_k=top_k)


class _ChromaBackend:
    def __init__(self, persist_dir: Path, collection_name: str):
        import chromadb

        self.client = chromadb.PersistentClient(path=str(persist_dir))
        self.collection = self.client.get_or_create_collection(name=collection_name)

    def add_chunks(self, chunks: list[DocumentChunk]) -> int:
        if not chunks:
            return 0

        ids = [str(uuid.uuid4()) for _ in chunks]
        documents = [chunk.text for chunk in chunks]
        embeddings = [hash_embedding(chunk.text) for chunk in chunks]
        metadatas = [
            {
                "source": chunk.source,
                "chunk_index": chunk.chunk_index,
                "page": chunk.page if chunk.page is not None else -1,
            }
            for chunk in chunks
        ]

        self.collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        return len(chunks)

    def delete_source(self, source: str) -> int:
        existing = self.collection.get(where={"source": source})
        ids = existing.get("ids", [])
        if not ids:
            return 0
        self.collection.delete(ids=ids)
        return len(ids)

    def query(self, question: str, top_k: int = 4) -> list[RetrievalHit]:
        result = self.collection.query(
            query_embeddings=[hash_embedding(question)],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        hits: list[RetrievalHit] = []
        for document, metadata, distance in zip(documents, metadatas, distances):
            page = metadata.get("page")
            hits.append(
                RetrievalHit(
                    text=document,
                    source=str(metadata.get("source", "unknown")),
                    chunk_index=metadata.get("chunk_index"),
                    page=None if page in (None, -1) else int(page),
                    score=None if distance is None else float(distance),
                )
            )
        return hits


class _JsonlBackend:
    def __init__(self, persist_dir: Path, collection_name: str):
        persist_dir.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", collection_name)
        self.path = persist_dir / f"{safe_name}.jsonl"

    def add_chunks(self, chunks: list[DocumentChunk]) -> int:
        if not chunks:
            return 0

        with self.path.open("a", encoding="utf-8") as output:
            for chunk in chunks:
                record = {
                    "id": str(uuid.uuid4()),
                    "text": chunk.text,
                    "embedding": hash_embedding(chunk.text),
                    "metadata": {
                        "source": chunk.source,
                        "chunk_index": chunk.chunk_index,
                        "page": chunk.page,
                    },
                }
                output.write(json.dumps(record, ensure_ascii=False) + "\n")
        return len(chunks)

    def delete_source(self, source: str) -> int:
        if not self.path.exists():
            return 0

        kept_records = []
        deleted = 0
        with self.path.open("r", encoding="utf-8") as input_file:
            for line in input_file:
                record = json.loads(line)
                metadata = record.get("metadata", {})
                if metadata.get("source") == source:
                    deleted += 1
                else:
                    kept_records.append(record)

        with self.path.open("w", encoding="utf-8") as output_file:
            for record in kept_records:
                output_file.write(json.dumps(record, ensure_ascii=False) + "\n")

        return deleted

    def query(self, question: str, top_k: int = 4) -> list[RetrievalHit]:
        if not self.path.exists():
            return []

        query_embedding = hash_embedding(question)
        scored_records = []
        with self.path.open("r", encoding="utf-8") as source:
            for line in source:
                record = json.loads(line)
                similarity = _cosine_similarity(query_embedding, record["embedding"])
                scored_records.append((similarity, record))

        hits: list[RetrievalHit] = []
        for similarity, record in sorted(scored_records, reverse=True)[:top_k]:
            metadata = record.get("metadata", {})
            hits.append(
                RetrievalHit(
                    text=record.get("text", ""),
                    source=str(metadata.get("source", "unknown")),
                    chunk_index=metadata.get("chunk_index"),
                    page=metadata.get("page"),
                    score=round(1.0 - similarity, 6),
                )
            )
        return hits


def _build_backend(persist_dir: Path, collection_name: str):
    try:
        return _ChromaBackend(persist_dir=persist_dir, collection_name=collection_name)
    except ModuleNotFoundError:
        return _JsonlBackend(persist_dir=persist_dir, collection_name=collection_name)


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    return sum(left_value * right_value for left_value, right_value in zip(left, right))


def hash_embedding(text: str, dimension: int = EMBEDDING_DIMENSION) -> list[float]:
    vector = [0.0] * dimension
    for token in _tokens(text):
        digest = hashlib.md5(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "little") % dimension
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _tokens(text: str) -> list[str]:
    lowered = text.lower()
    ascii_tokens = re.findall(r"[a-z0-9_]+", lowered)
    cjk_chars = re.findall(r"[\u4e00-\u9fff]", lowered)
    cjk_bigrams = [
        "".join(cjk_chars[index : index + 2])
        for index in range(max(0, len(cjk_chars) - 1))
    ]
    return ascii_tokens + cjk_chars + cjk_bigrams
