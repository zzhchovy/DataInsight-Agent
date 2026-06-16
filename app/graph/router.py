from dataclasses import dataclass


@dataclass(frozen=True)
class RouteDecision:
    route: str
    reason: str
    confidence: float
    matched_keywords: list[str]


REPORT_KEYWORDS = [
    "report",
    "summary",
    "summarize",
    "总结",
    "报告",
    "归纳",
]

CHART_KEYWORDS = [
    "chart",
    "plot",
    "draw",
    "visual",
    "trend",
    "图表",
    "画图",
    "趋势图",
    "可视化",
    "趋势",
]

DATA_KEYWORDS = [
    "average",
    "mean",
    "avg",
    "max",
    "min",
    "correlation",
    "corr",
    "describe",
    "rows",
    "columns",
    "平均",
    "平均值",
    "均值",
    "最大",
    "最小",
    "相关",
    "统计",
    "列名",
    "字段",
    "数据中",
    "上传数据",
]


def route_question(question: str) -> str:
    return classify_question(question).route


def classify_question(question: str) -> RouteDecision:
    normalized = question.lower()

    report_matches = _matched_keywords(normalized, REPORT_KEYWORDS)
    chart_matches = _matched_keywords(normalized, CHART_KEYWORDS)
    data_matches = _matched_keywords(normalized, DATA_KEYWORDS)

    if report_matches:
        return RouteDecision(
            route="report",
            reason="问题包含总结/报告类意图，优先生成结构化报告。",
            confidence=_confidence(report_matches),
            matched_keywords=report_matches,
        )

    if chart_matches:
        return RouteDecision(
            route="chart",
            reason="问题包含图表/趋势/可视化意图，调用图表工具。",
            confidence=_confidence(chart_matches),
            matched_keywords=chart_matches,
        )

    if data_matches:
        return RouteDecision(
            route="data",
            reason="问题包含统计/指标/字段类意图，调用 pandas 数据分析工具。",
            confidence=_confidence(data_matches),
            matched_keywords=data_matches,
        )

    return RouteDecision(
        route="rag",
        reason="未命中工具类关键词，默认作为资料查询走 RAG。",
        confidence=0.55,
        matched_keywords=[],
    )


def _matched_keywords(text: str, keywords: list[str]) -> list[str]:
    return [keyword for keyword in keywords if keyword in text]


def _confidence(matches: list[str]) -> float:
    return min(0.95, 0.72 + 0.08 * len(matches))
