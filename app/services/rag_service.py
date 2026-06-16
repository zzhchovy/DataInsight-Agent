from app.retrieval.base import RetrievalRequest, RetrievedChunk
from app.retrieval.service import RetrievalService
from app.services.llm_service import LLMContext, generate_rag_answer


def answer_with_rag(question: str, top_k: int = 4) -> dict:
    retrieval_result = RetrievalService().retrieve(
        RetrievalRequest(question=question, top_k=top_k)
    )
    chunks = retrieval_result.retrieved_chunks

    if not chunks:
        notice = retrieval_result.backend_notice or "没有检索到相关文档内容。"
        return {
            "answer": f"{notice} 请先上传文档，或换一种更接近文档内容的问法。",
            "citations": [],
            "retrieval_backend": retrieval_result.retrieval_backend,
            "selected_corpora": retrieval_result.selected_corpora,
            "rewritten_queries": retrieval_result.rewritten_queries,
            "retrieval_rounds": [
                item.to_dict() for item in retrieval_result.retrieval_rounds
            ],
            "sufficient_context": retrieval_result.sufficient_context,
            "retrieved_chunks": [],
            "used_llm": False,
            "llm_used": False,
            "llm_provider": None,
            "llm_model": None,
            "latency_ms": retrieval_result.latency_ms,
            "backend_notice": retrieval_result.backend_notice,
            "uncertainty": "当前没有可用的检索上下文，因此答案可能不完整。",
        }

    contexts = [
        _chunk_to_llm_context(chunk)
        for chunk in chunks
    ]
    llm_result = generate_rag_answer(question=question, contexts=contexts)

    if llm_result.used_llm:
        answer = llm_result.text
        uncertainty = (
            "回答由外部大模型基于 Agentic RAG 检索片段综合生成。"
            "请结合引用来源复核关键结论，尤其是涉及业务决策或工程判断的部分。"
        )
    else:
        answer = _build_extractive_answer(question=question, chunks=chunks)
        uncertainty = (
            f"{llm_result.text} 当前回答基于本地 Agentic RAG 检索片段直接组织，"
            "没有经过大模型综合生成，语义概括能力有限。"
        )
        if llm_result.error:
            uncertainty += f" LLM 状态：{llm_result.error}"

    if retrieval_result.backend_notice:
        uncertainty = f"{retrieval_result.backend_notice} {uncertainty}"

    return {
        "answer": answer,
        "citations": retrieval_result.citations,
        "retrieval_backend": retrieval_result.retrieval_backend,
        "selected_corpora": retrieval_result.selected_corpora,
        "rewritten_queries": retrieval_result.rewritten_queries,
        "retrieval_rounds": [item.to_dict() for item in retrieval_result.retrieval_rounds],
        "sufficient_context": retrieval_result.sufficient_context,
        "retrieved_chunks": [chunk.to_dict() for chunk in chunks],
        "used_llm": llm_result.used_llm,
        "llm_used": llm_result.used_llm,
        "llm_provider": llm_result.provider,
        "llm_model": llm_result.model,
        "latency_ms": retrieval_result.latency_ms,
        "backend_notice": retrieval_result.backend_notice,
        "uncertainty": uncertainty,
    }


def _build_extractive_answer(question: str, chunks: list[RetrievedChunk]) -> str:
    snippets = []
    for chunk in chunks:
        snippets.append(f"[{chunk.label}] {chunk.text[:500]}")

    return (
        f"针对问题“{question}”，当前 Agentic RAG 检索到的主要依据如下：\n\n"
        + "\n\n".join(snippets)
        + "\n\n本地 fallback 说明：当前未启用可用的大模型综合回答，因此先返回可追溯的检索依据。"
    )


def _chunk_to_llm_context(chunk: RetrievedChunk) -> LLMContext:
    return LLMContext(
        label=chunk.label,
        source=chunk.source,
        content=chunk.text[:1200],
        page=chunk.page,
    )
