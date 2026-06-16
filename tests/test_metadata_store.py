from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.services.metadata_store import (
    init_metadata_db,
    list_artifacts,
    list_datasets_metadata,
    list_documents,
    list_qa_history,
    record_agent_run,
    record_dataset,
    record_document,
)


def test_metadata_store_records_core_entities(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAINSIGHT_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()

    try:
        init_metadata_db()
        record_document(
            file_id="doc-1.md",
            filename="boiler.md",
            file_type="md",
            corpus="energy_demo",
            chunk_count=3,
            saved_path=str(tmp_path / "boiler.md"),
        )
        record_dataset(
            dataset_id="data-1.csv",
            filename="plant.csv",
            file_type="csv",
            row_count=2,
            columns=["date", "efficiency"],
            saved_path=str(tmp_path / "plant.csv"),
        )
        qa_id = record_agent_run(
            question="画出 efficiency 趋势图",
            dataset_id="data-1.csv",
            state={
                "route": "chart",
                "answer": "图表已生成。",
                "final_answer": "图表已生成。",
                "chart_path": str(tmp_path / "chart.png"),
                "artifacts": {"chart_path": str(tmp_path / "chart.png")},
                "citations": [],
                "selected_corpora": [],
                "latency_ms": 12,
            },
        )

        documents = list_documents()
        datasets = list_datasets_metadata()
        history = list_qa_history()
        artifacts = list_artifacts()

        assert documents[0]["id"] == "doc-1.md"
        assert documents[0]["corpus"] == "energy_demo"
        assert datasets[0]["columns"] == ["date", "efficiency"]
        assert history[0]["id"] == qa_id
        assert history[0]["route"] == "chart"
        assert artifacts[0]["artifact_type"] == "chart"
    finally:
        get_settings.cache_clear()


def test_metadata_endpoints_include_qa_history(tmp_path, monkeypatch):
    monkeypatch.setenv("DATAINSIGHT_STORAGE_DIR", str(tmp_path))
    get_settings.cache_clear()

    import app.main as main

    def fake_run_agent(question: str, dataset_id: str | None = None, top_k: int = 4):
        return {
            "route": "rag",
            "router_reason": "测试路由。",
            "route_confidence": 0.9,
            "matched_keywords": [],
            "answer": "测试回答。",
            "final_answer": "测试回答。",
            "citations": [
                {
                    "label": "来源1",
                    "source": "demo.md",
                    "corpus": "general_docs",
                    "preview": "测试引用。",
                }
            ],
            "retrieval_backend": "local_agentic_rag",
            "selected_corpora": ["general_docs"],
            "rewritten_queries": [question],
            "retrieval_rounds": [],
            "sufficient_context": True,
            "retrieved_chunks": [],
            "used_llm": False,
            "latency_ms": 5,
            "tool_calls": [],
            "artifacts": {},
            "llm_used": False,
        }

    monkeypatch.setattr(main, "run_agent", fake_run_agent)

    try:
        with TestClient(main.app) as client:
            ask_response = client.post("/ask", json={"question": "测试问题"})
            history_response = client.get("/metadata/history")

        assert ask_response.status_code == 200
        assert history_response.status_code == 200
        history = history_response.json()
        assert history[0]["question"] == "测试问题"
        assert history[0]["retrieval_backend"] == "local_agentic_rag"
        assert history[0]["selected_corpora"] == ["general_docs"]
        assert history[0]["citations"][0]["source"] == "demo.md"
    finally:
        get_settings.cache_clear()
