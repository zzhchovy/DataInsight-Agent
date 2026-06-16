from app.core.config import get_settings
from app.services.llm_service import LLMContext, generate_rag_answer


def test_generate_rag_answer_disabled_provider(monkeypatch):
    monkeypatch.setenv("DATAINSIGHT_LLM_PROVIDER", "none")
    get_settings.cache_clear()

    result = generate_rag_answer(
        question="根据文档，影响锅炉效率的因素有哪些？",
        contexts=[
            LLMContext(
                label="来源1",
                source="boiler_efficiency.md",
                content="锅炉效率受到燃烧质量、过量空气系数和排烟温度影响。",
            )
        ],
    )

    assert result.used_llm is False
    assert "回退" in result.text
    get_settings.cache_clear()

