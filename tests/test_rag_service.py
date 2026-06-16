from app.retrieval.base import RetrievalResult, RetrievalRound, RetrievedChunk
from app.services import rag_service
from app.services.llm_service import LLMResult


class FakeRetrievalService:
    def retrieve(self, request):
        chunk = RetrievedChunk(
            label="来源1",
            text="锅炉效率受到燃烧质量、过量空气系数和排烟温度影响。",
            source="boiler_efficiency.md",
            corpus="energy_demo",
            chunk_index=0,
            score=0.1,
        )
        return RetrievalResult(
            answer=None,
            retrieval_backend="local_agentic_rag",
            selected_corpora=["energy_demo"],
            rewritten_queries=[
                "根据文档，影响锅炉效率的因素有哪些？",
                "锅炉效率 燃烧质量 过量空气系数 排烟温度 受热面",
            ],
            retrieval_rounds=[
                RetrievalRound(
                    round_index=1,
                    queries=["根据文档，影响锅炉效率的因素有哪些？"],
                    corpora=["energy_demo"],
                    top_k=4,
                    retrieved_count=1,
                    accepted_count=1,
                    sufficient_context=True,
                    notes="测试证据足够。",
                )
            ],
            sufficient_context=True,
            citations=[
                {
                    "label": "来源1",
                    "source": "boiler_efficiency.md",
                    "corpus": "energy_demo",
                    "preview": "锅炉效率受到燃烧质量、过量空气系数和排烟温度影响。",
                }
            ],
            retrieved_chunks=[chunk],
            used_llm=False,
            latency_ms=3,
        )


def test_rag_fallback_answer_has_agentic_trace(monkeypatch):
    monkeypatch.setattr(rag_service, "RetrievalService", lambda: FakeRetrievalService())
    monkeypatch.setattr(
        rag_service,
        "generate_rag_answer",
        lambda question, contexts: LLMResult(
            text="未启用外部大模型，已回退到本地检索片段式回答。",
            used_llm=False,
            provider="none",
        ),
    )

    result = rag_service.answer_with_rag("根据文档，影响锅炉效率的因素有哪些？")

    assert result["llm_used"] is False
    assert result["retrieval_backend"] == "local_agentic_rag"
    assert result["selected_corpora"] == ["energy_demo"]
    assert result["rewritten_queries"]
    assert result["retrieval_rounds"][0]["sufficient_context"] is True
    assert result["sufficient_context"] is True
    assert result["retrieved_chunks"][0]["corpus"] == "energy_demo"
    assert "[来源1]" in result["answer"]


def test_rag_llm_answer_is_used_when_available(monkeypatch):
    monkeypatch.setattr(rag_service, "RetrievalService", lambda: FakeRetrievalService())
    monkeypatch.setattr(
        rag_service,
        "generate_rag_answer",
        lambda question, contexts: LLMResult(
            text="锅炉效率主要受燃烧质量、过量空气系数和排烟温度影响。[来源1]",
            used_llm=True,
            provider="openai",
            model="demo-model",
        ),
    )

    result = rag_service.answer_with_rag("根据文档，影响锅炉效率的因素有哪些？")

    assert result["llm_used"] is True
    assert result["used_llm"] is True
    assert result["llm_provider"] == "openai"
    assert result["llm_model"] == "demo-model"
    assert "锅炉效率主要受" in result["answer"]
