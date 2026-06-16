from app.services.rag_service import answer_with_rag
from app.tools.pandas_tool import analysis_to_text, analyze_dataframe


def build_report(question: str, dataframe=None, top_k: int = 4) -> dict:
    rag_result = answer_with_rag(question, top_k=top_k)
    sections = ["# DataInsight-Agent 运行分析报告"]

    if rag_result.get("citations"):
        sections.append("## 一、文档依据")
        sections.append(rag_result["answer"])

    analysis = None
    if dataframe is not None:
        analysis = analyze_dataframe(question, dataframe)
        sections.append("## 二、数据分析")
        sections.append(analysis_to_text(analysis))

    sections.append("## 三、初步结论")
    sections.append(
        "本报告综合了已检索到的文档依据和已上传的结构化数据。"
        "当前版本用于 MVP 演示，后续可以在工具执行后接入大模型，生成更完整的业务化分析结论。"
    )

    return {
        "answer": "\n\n".join(sections),
        "citations": rag_result.get("citations", []),
        "retrieval_backend": rag_result.get("retrieval_backend"),
        "selected_corpora": rag_result.get("selected_corpora", []),
        "rewritten_queries": rag_result.get("rewritten_queries", []),
        "retrieval_rounds": rag_result.get("retrieval_rounds", []),
        "sufficient_context": rag_result.get("sufficient_context"),
        "retrieved_chunks": rag_result.get("retrieved_chunks", []),
        "used_llm": rag_result.get("used_llm", rag_result.get("llm_used", False)),
        "latency_ms": rag_result.get("latency_ms"),
        "backend_notice": rag_result.get("backend_notice"),
        "analysis": analysis,
        "llm_used": rag_result.get("llm_used", False),
        "llm_provider": rag_result.get("llm_provider"),
        "llm_model": rag_result.get("llm_model"),
        "uncertainty": "当前报告为模板化 MVP 输出，正式业务使用前需要结合现场日志、检修记录和燃料数据复核。",
    }
