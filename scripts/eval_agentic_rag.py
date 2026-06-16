import json
from pathlib import Path
import statistics
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.graph.workflow import run_agent
from app.core.paths import storage_root
from scripts.ingest_energy_demo import DEMO_DATASET_ID, main as ingest_energy_demo


EVAL_CASES = [
    {
        "id": "rag_energy_factors",
        "question": "根据文档，影响锅炉效率的因素有哪些？",
        "expected_route": "rag",
        "expected_backend": "local_agentic_rag",
        "expected_corpus": "energy_demo",
        "requires_citation": True,
        "requires_sufficient_context": True,
    },
    {
        "id": "data_mean_efficiency",
        "question": "上传数据中 boiler_efficiency_pct 的平均值是多少？",
        "expected_route": "data",
        "requires_citation": False,
    },
    {
        "id": "chart_trend",
        "question": "画出 load_mw 和 boiler_efficiency_pct 的趋势图。",
        "expected_route": "chart",
        "requires_chart": True,
    },
    {
        "id": "report_operation",
        "question": "生成一份简短的运行分析报告。",
        "expected_route": "report",
        "expected_backend": "local_agentic_rag",
        "expected_corpus": "energy_demo",
        "requires_citation": True,
    },
    {
        "id": "insufficient_evidence",
        "question": "根据文档，说明汽轮机叶片裂纹的检修流程。",
        "expected_route": "rag",
        "expected_backend": "local_agentic_rag",
        "requires_sufficient_context": False,
    },
]


def main() -> None:
    ingest_energy_demo()
    results = []
    for case in EVAL_CASES:
        state = run_agent(case["question"], dataset_id=DEMO_DATASET_ID)
        result = evaluate_case(case, state)
        results.append(result)

    summary = build_summary(results)
    report = {"summary": summary, "results": results}
    output_path = write_report(report)

    print_eval_report(report)
    print(f"\n评测报告已写入：{output_path}")


def evaluate_case(case: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
    route_ok = state.get("route") == case["expected_route"]
    backend_ok = (
        case.get("expected_backend") is None
        or state.get("retrieval_backend") == case.get("expected_backend")
    )
    corpora = state.get("selected_corpora", [])
    corpus_ok = (
        case.get("expected_corpus") is None
        or case["expected_corpus"] in corpora
    )
    citation_ok = (not case.get("requires_citation")) or bool(state.get("citations"))
    chart_ok = (not case.get("requires_chart")) or bool(state.get("chart_path"))

    if "requires_sufficient_context" in case:
        sufficient_context_ok = (
            state.get("sufficient_context") is case["requires_sufficient_context"]
        )
    else:
        sufficient_context_ok = True

    answer_has_citation_label = (
        not case.get("requires_citation")
        or "来源" in state.get("answer", "")
        or bool(state.get("citations"))
    )
    latency_ms = state.get("latency_ms")

    passed = all(
        [
            route_ok,
            backend_ok,
            corpus_ok,
            citation_ok,
            chart_ok,
            sufficient_context_ok,
            answer_has_citation_label,
        ]
    )

    return {
        "id": case["id"],
        "question": case["question"],
        "passed": passed,
        "route": state.get("route"),
        "expected_route": case["expected_route"],
        "route_ok": route_ok,
        "retrieval_backend": state.get("retrieval_backend"),
        "backend_ok": backend_ok,
        "selected_corpora": corpora,
        "rewritten_queries": state.get("rewritten_queries", []),
        "retrieval_rounds": state.get("retrieval_rounds", []),
        "sufficient_context": state.get("sufficient_context"),
        "sufficient_context_ok": sufficient_context_ok,
        "citations_count": len(state.get("citations", [])),
        "citation_ok": citation_ok,
        "answer_has_citation_label": answer_has_citation_label,
        "chart_path": state.get("chart_path"),
        "chart_ok": chart_ok,
        "latency_ms": latency_ms,
        "tool_calls": [
            item.get("tool_name") for item in state.get("tool_calls", [])
        ],
        "answer_preview": state.get("answer", "")[:240],
        "uncertainty": state.get("uncertainty"),
    }


def build_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    route_accuracy = ratio(item["route_ok"] for item in results)
    citation_accuracy = ratio(
        item["citation_ok"]
        for item in results
        if item["id"] in {"rag_energy_factors", "report_operation"}
    )
    rag_cases = [
        item for item in results if item["retrieval_backend"] == "local_agentic_rag"
    ]
    rag_recall_hit_rate = ratio(
        "energy_demo" in item["selected_corpora"]
        for item in rag_cases
        if item["id"] != "insufficient_evidence"
    )
    insufficient_handling_rate = ratio(
        item["sufficient_context"] is False
        for item in results
        if item["id"] == "insufficient_evidence"
    )
    latencies = [
        item["latency_ms"]
        for item in results
        if isinstance(item.get("latency_ms"), int)
    ]

    return {
        "total_cases": len(results),
        "passed_cases": sum(1 for item in results if item["passed"]),
        "pass_rate": round(ratio(item["passed"] for item in results), 4),
        "route_accuracy": round(route_accuracy, 4),
        "rag_recall_hit_rate": round(rag_recall_hit_rate, 4),
        "citation_accuracy": round(citation_accuracy, 4),
        "insufficient_evidence_handling_rate": round(insufficient_handling_rate, 4),
        "latency_ms_avg": round(statistics.mean(latencies), 2) if latencies else None,
        "latency_ms_max": max(latencies) if latencies else None,
    }


def ratio(values) -> float:
    values = list(values)
    if not values:
        return 0.0
    return sum(1 for value in values if value) / len(values)


def write_report(report: dict[str, Any]) -> Path:
    output_dir = storage_root() / "eval_reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "agentic_rag_eval.json"
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def print_eval_report(report: dict[str, Any]) -> None:
    summary = report["summary"]
    print("\n=== DataInsight-Agent 评测摘要 ===")
    for key, value in summary.items():
        print(f"{key}: {value}")

    print("\n=== Case 明细 ===")
    for item in report["results"]:
        print("-" * 80)
        print(f"[{item['id']}] passed={item['passed']}")
        print(f"question: {item['question']}")
        print(f"route: {item['route']} / expected={item['expected_route']}")
        print(f"retrieval_backend: {item['retrieval_backend']}")
        print(f"selected_corpora: {item['selected_corpora']}")
        print(f"rewritten_queries: {item['rewritten_queries']}")
        print(f"sufficient_context: {item['sufficient_context']}")
        print(f"citations_count: {item['citations_count']}")
        print(f"latency_ms: {item['latency_ms']}")
        print(f"tool_calls: {item['tool_calls']}")


if __name__ == "__main__":
    main()
