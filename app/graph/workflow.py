from typing import Any

from app.graph.router import classify_question
from app.graph.state import AgentState
from app.services.chart_service import run_chart_tool
from app.services.data_service import load_dataset
from app.services.rag_service import answer_with_rag
from app.services.report_service import build_report
from app.tools.pandas_tool import run_pandas_analysis_tool


def run_agent(question: str, dataset_id: str | None = None, top_k: int = 4) -> AgentState:
    initial_state: AgentState = {
        "question": question,
        "dataset_id": dataset_id,
        "top_k": top_k,
        "tool_calls": [],
        "artifacts": {},
    }
    try:
        graph = build_graph()
        return _ensure_final_fields(graph.invoke(initial_state))
    except ModuleNotFoundError:
        return _ensure_final_fields(run_agent_without_langgraph(initial_state))


def build_graph():
    from langgraph.graph import END, START, StateGraph

    workflow = StateGraph(AgentState)
    workflow.add_node("router", _router_node)
    workflow.add_node("rag", _rag_node)
    workflow.add_node("data", _data_node)
    workflow.add_node("chart", _chart_node)
    workflow.add_node("report", _report_node)

    workflow.add_edge(START, "router")
    workflow.add_conditional_edges(
        "router",
        lambda state: state["route"],
        {
            "rag": "rag",
            "data": "data",
            "chart": "chart",
            "report": "report",
        },
    )
    workflow.add_edge("rag", END)
    workflow.add_edge("data", END)
    workflow.add_edge("chart", END)
    workflow.add_edge("report", END)
    return workflow.compile()


def run_agent_without_langgraph(state: AgentState) -> AgentState:
    routed = _router_node(state)
    route = routed["route"]
    if route == "rag":
        return _rag_node(routed)
    if route == "data":
        return _data_node(routed)
    if route == "chart":
        return _chart_node(routed)
    if route == "report":
        return _report_node(routed)
    return _rag_node(routed)


def _router_node(state: AgentState) -> AgentState:
    decision = classify_question(state["question"])
    return {
        **state,
        "route": decision.route,
        "router_reason": decision.reason,
        "route_confidence": decision.confidence,
        "matched_keywords": decision.matched_keywords,
    }


def _rag_node(state: AgentState) -> AgentState:
    result = answer_with_rag(state["question"], top_k=state.get("top_k", 4))
    tool_call = {
        "tool_name": "rag_retrieval",
        "success": True,
        "summary": "已完成文档检索与可选 LLM 综合回答。",
        "data": {
            "citation_count": len(result.get("citations", [])),
            "retrieval_backend": result.get("retrieval_backend"),
            "selected_corpora": result.get("selected_corpora", []),
            "rewritten_queries": result.get("rewritten_queries", []),
            "sufficient_context": result.get("sufficient_context"),
            "latency_ms": result.get("latency_ms"),
            "llm_used": result.get("llm_used", False),
            "llm_provider": result.get("llm_provider"),
            "llm_model": result.get("llm_model"),
        },
        "artifacts": {},
        "uncertainty": result.get("uncertainty"),
        "error": None,
    }
    return {
        **state,
        **result,
        "analysis": None,
        "chart_path": None,
        "tool_calls": _append_tool_call(state, tool_call),
        "artifacts": _merge_artifacts(state, {}),
    }


def _data_node(state: AgentState) -> AgentState:
    try:
        dataframe = load_dataset(state.get("dataset_id"))
        result = run_pandas_analysis_tool(state["question"], dataframe)
        return {
            **state,
            "answer": result.summary,
            "analysis": result.data.get("analysis"),
            "citations": [],
            "chart_path": None,
            "tool_calls": _append_tool_call(state, result.to_tool_call()),
            "artifacts": _merge_artifacts(state, result.artifacts),
            "uncertainty": result.uncertainty,
        }
    except Exception as exc:
        return _error_state(state, exc, tool_name="pandas_analysis")


def _chart_node(state: AgentState) -> AgentState:
    try:
        dataframe = load_dataset(state.get("dataset_id"))
        result = run_chart_tool(state["question"], dataframe)
        chart_path = result.artifacts.get("chart_path")
        return {
            **state,
            "answer": result.summary,
            "analysis": None,
            "citations": [],
            "chart_path": chart_path,
            "tool_calls": _append_tool_call(state, result.to_tool_call()),
            "artifacts": _merge_artifacts(state, result.artifacts),
            "uncertainty": result.uncertainty,
        }
    except Exception as exc:
        return _error_state(state, exc, tool_name="chart_generation")


def _report_node(state: AgentState) -> AgentState:
    dataframe = None
    try:
        dataframe = load_dataset(state.get("dataset_id"))
    except Exception:
        dataframe = None

    result = build_report(
        state["question"],
        dataframe=dataframe,
        top_k=state.get("top_k", 4),
    )
    tool_call = {
        "tool_name": "report_generation",
        "success": True,
        "summary": "已生成结构化分析报告。",
        "data": {
            "has_dataset": dataframe is not None,
            "citation_count": len(result.get("citations", [])),
            "retrieval_backend": result.get("retrieval_backend"),
            "selected_corpora": result.get("selected_corpora", []),
            "sufficient_context": result.get("sufficient_context"),
            "latency_ms": result.get("latency_ms"),
            "llm_used": result.get("llm_used", False),
        },
        "artifacts": {},
        "uncertainty": result.get("uncertainty"),
        "error": None,
    }
    return {
        **state,
        **result,
        "chart_path": None,
        "tool_calls": _append_tool_call(state, tool_call),
        "artifacts": _merge_artifacts(state, {}),
    }


def _error_state(state: AgentState, exc: Exception, tool_name: str = "unknown") -> AgentState:
    tool_call = {
        "tool_name": tool_name,
        "success": False,
        "summary": f"工具执行失败：{exc}",
        "data": {},
        "artifacts": {},
        "uncertainty": "所选工具未能完成任务，请检查是否已上传对应文件，或把问题描述得更明确。",
        "error": str(exc),
    }
    return {
        **state,
        "answer": tool_call["summary"],
        "analysis": None,
        "citations": [],
        "chart_path": None,
        "tool_calls": _append_tool_call(state, tool_call),
        "artifacts": _merge_artifacts(state, {}),
        "uncertainty": tool_call["uncertainty"],
        "error": str(exc),
    }


def _append_tool_call(state: AgentState, tool_call: dict[str, Any]) -> list[dict[str, Any]]:
    return [*state.get("tool_calls", []), tool_call]


def _merge_artifacts(state: AgentState, artifacts: dict[str, Any]) -> dict[str, Any]:
    return {**state.get("artifacts", {}), **artifacts}


def _ensure_final_fields(state: AgentState) -> AgentState:
    answer = state.get("answer", "")
    return {
        **state,
        "answer": answer,
        "final_answer": state.get("final_answer") or answer,
        "tool_calls": state.get("tool_calls", []),
        "artifacts": state.get("artifacts", {}),
        "citations": state.get("citations", []),
        "llm_used": state.get("llm_used", False),
        "used_llm": state.get("used_llm", state.get("llm_used", False)),
        "selected_corpora": state.get("selected_corpora", []),
        "rewritten_queries": state.get("rewritten_queries", []),
        "retrieval_rounds": state.get("retrieval_rounds", []),
        "retrieved_chunks": state.get("retrieved_chunks", []),
        "sufficient_context": state.get("sufficient_context"),
        "latency_ms": state.get("latency_ms"),
        "backend_notice": state.get("backend_notice"),
    }
