from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RetrievalRequest:
    question: str
    top_k: int = 4


@dataclass(frozen=True)
class RetrievedChunk:
    label: str
    text: str
    source: str
    corpus: str
    chunk_index: int | None = None
    page: int | None = None
    score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "text": self.text,
            "source": self.source,
            "corpus": self.corpus,
            "chunk_index": self.chunk_index,
            "page": self.page,
            "score": self.score,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class RetrievalRound:
    round_index: int
    queries: list[str]
    corpora: list[str]
    top_k: int
    retrieved_count: int
    accepted_count: int
    sufficient_context: bool
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_index": self.round_index,
            "queries": self.queries,
            "corpora": self.corpora,
            "top_k": self.top_k,
            "retrieved_count": self.retrieved_count,
            "accepted_count": self.accepted_count,
            "sufficient_context": self.sufficient_context,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class RetrievalResult:
    answer: str | None
    retrieval_backend: str
    selected_corpora: list[str]
    rewritten_queries: list[str]
    retrieval_rounds: list[RetrievalRound]
    sufficient_context: bool
    citations: list[dict[str, Any]]
    retrieved_chunks: list[RetrievedChunk]
    used_llm: bool
    latency_ms: int
    backend_notice: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_trace_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "retrieval_backend": self.retrieval_backend,
            "selected_corpora": self.selected_corpora,
            "rewritten_queries": self.rewritten_queries,
            "retrieval_rounds": [item.to_dict() for item in self.retrieval_rounds],
            "sufficient_context": self.sufficient_context,
            "citations": self.citations,
            "retrieved_chunks": [item.to_dict() for item in self.retrieved_chunks],
            "used_llm": self.used_llm,
            "latency_ms": self.latency_ms,
            "backend_notice": self.backend_notice,
            "metadata": self.metadata,
        }


class BaseRetriever(ABC):
    backend_name: str

    @abstractmethod
    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        raise NotImplementedError
