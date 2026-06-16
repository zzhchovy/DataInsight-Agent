from app.core.config import get_settings
from app.retrieval.base import RetrievalRequest, RetrievalResult, RetrievalRound, RetrievedChunk
from app.retrieval.local_agentic import (
    check_evidence,
    rewrite_query,
    route_corpora,
)
from app.retrieval.service import RetrievalService


def test_local_query_rewrite_and_corpus_router():
    question = "根据文档，影响锅炉效率的因素有哪些？"

    queries = rewrite_query(question)
    corpora = route_corpora(question)

    assert len(queries) >= 2
    assert "energy_demo" in corpora


def test_local_evidence_checker_can_mark_energy_context_sufficient():
    class Hit:
        text = "锅炉效率受到燃烧质量、过量空气系数和排烟温度影响。"

    result = check_evidence("影响锅炉效率的因素有哪些？", [Hit()])

    assert result.sufficient is True


class FakeLocalRetriever:
    def retrieve(self, request):
        chunk = RetrievedChunk(
            label="来源1",
            text="本地 fallback 证据。",
            source="local.md",
            corpus="general_docs",
        )
        return RetrievalResult(
            answer=None,
            retrieval_backend="local_agentic_rag",
            selected_corpora=["general_docs"],
            rewritten_queries=[request.question],
            retrieval_rounds=[
                RetrievalRound(
                    round_index=1,
                    queries=[request.question],
                    corpora=["general_docs"],
                    top_k=request.top_k,
                    retrieved_count=1,
                    accepted_count=1,
                    sufficient_context=True,
                )
            ],
            sufficient_context=True,
            citations=[],
            retrieved_chunks=[chunk],
            used_llm=False,
            latency_ms=1,
        )


def test_google_backend_missing_config_falls_back_to_local(monkeypatch):
    monkeypatch.setenv("RETRIEVAL_BACKEND", "google_agentic_rag")
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_RAG_CORPUS_IDS", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    get_settings.cache_clear()

    result = RetrievalService(local_retriever=FakeLocalRetriever()).retrieve(
        RetrievalRequest(question="测试问题")
    )

    assert result.retrieval_backend == "local_agentic_rag"
    assert result.backend_notice
    assert "Google Agentic RAG 未配置" in result.backend_notice
    get_settings.cache_clear()
