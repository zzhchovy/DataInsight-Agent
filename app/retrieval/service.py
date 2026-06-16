from app.core.config import get_settings
from app.retrieval.base import RetrievalRequest, RetrievalResult
from app.retrieval.google_agentic import GoogleAgenticRagRetriever
from app.retrieval.local_agentic import LocalAgenticRagRetriever


class RetrievalService:
    def __init__(
        self,
        local_retriever: LocalAgenticRagRetriever | None = None,
        google_retriever: GoogleAgenticRagRetriever | None = None,
    ):
        self.local_retriever = local_retriever or LocalAgenticRagRetriever()
        self.google_retriever = google_retriever or GoogleAgenticRagRetriever()

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        settings = get_settings()
        backend = settings.retrieval_backend.lower().strip()

        if backend == "google_agentic_rag":
            if not self.google_retriever.is_configured():
                missing = ", ".join(self.google_retriever.missing_config_fields())
                local_result = self.local_retriever.retrieve(request)
                return _with_notice(
                    local_result,
                    f"Google Agentic RAG 未配置，缺少：{missing}。已回退本地 Agentic RAG。",
                )

            google_result = self.google_retriever.retrieve(request)
            if google_result.retrieved_chunks:
                return google_result

            local_result = self.local_retriever.retrieve(request)
            return _with_notice(
                local_result,
                google_result.backend_notice
                or "Google Agentic RAG 适配层未返回上下文，已回退本地 Agentic RAG。",
            )

        if backend != "local_agentic_rag":
            local_result = self.local_retriever.retrieve(request)
            return _with_notice(
                local_result,
                f"未知 RETRIEVAL_BACKEND={settings.retrieval_backend}，已回退本地 Agentic RAG。",
            )

        return self.local_retriever.retrieve(request)


def _with_notice(result: RetrievalResult, notice: str) -> RetrievalResult:
    return RetrievalResult(
        answer=result.answer,
        retrieval_backend=result.retrieval_backend,
        selected_corpora=result.selected_corpora,
        rewritten_queries=result.rewritten_queries,
        retrieval_rounds=result.retrieval_rounds,
        sufficient_context=result.sufficient_context,
        citations=result.citations,
        retrieved_chunks=result.retrieved_chunks,
        used_llm=result.used_llm,
        latency_ms=result.latency_ms,
        backend_notice=notice,
        metadata={**result.metadata, "fallback_notice": notice},
    )
