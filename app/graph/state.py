from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    question: str
    dataset_id: str | None
    top_k: int
    route: str
    router_reason: str
    route_confidence: float
    matched_keywords: list[str]
    answer: str
    final_answer: str
    citations: list[dict]
    retrieval_backend: str | None
    selected_corpora: list[str]
    rewritten_queries: list[str]
    retrieval_rounds: list[dict[str, Any]]
    sufficient_context: bool | None
    retrieved_chunks: list[dict[str, Any]]
    used_llm: bool
    latency_ms: int | None
    backend_notice: str | None
    analysis: dict | None
    chart_path: str | None
    tool_calls: list[dict[str, Any]]
    artifacts: dict[str, Any]
    llm_used: bool
    llm_provider: str | None
    llm_model: str | None
    uncertainty: str | None
    error: str | None
