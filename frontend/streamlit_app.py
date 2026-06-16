from __future__ import annotations

import html
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import pandas as pd
import streamlit as st


APP_VERSION = "DataInsight-Agent v0.1.0"
DEFAULT_API_BASE_URL = os.getenv("DATAINSIGHT_API_BASE_URL", "http://127.0.0.1:8000")
DEFAULT_QUESTION = "根据文档，影响锅炉效率的因素有哪些？"
ROOT_DIR = Path(__file__).resolve().parents[1]
ENERGY_DOC_PATH = ROOT_DIR / "examples" / "energy_demo" / "docs" / "boiler_efficiency.md"
ENERGY_DATA_PATH = ROOT_DIR / "examples" / "energy_demo" / "data" / "plant_daily.csv"
LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")


ROUTE_LABELS = {
    "rag": "文档问答",
    "data": "数据分析",
    "chart": "图表生成",
    "report": "报告生成",
}

TOOL_LABELS = {
    "rag_retrieval": "rag_search_tool",
    "pandas_analysis": "data_analysis_tool",
    "chart_generation": "chart_tool",
    "report_generation": "report_tool",
}

ENERGY_DEMO_QUESTIONS = {
    "文档问答": DEFAULT_QUESTION,
    "数据分析": "上传数据中 boiler_efficiency_pct 的平均值是多少？",
    "图表生成": "画出 load_mw 和 boiler_efficiency_pct 的趋势图。",
    "报告生成": "生成一份简短的运行分析报告。",
}


st.set_page_config(
    page_title="DataInsight-Agent",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)


def main() -> None:
    init_state()
    inject_css()

    with st.sidebar:
        render_sidebar()

    api_base_url = st.session_state.api_base_url.rstrip("/")
    health = get_json(api_base_url, "/health")
    documents = unique_metadata_records(get_json(api_base_url, "/metadata/documents?limit=30", default=[]))
    datasets = unique_metadata_records(get_json(api_base_url, "/metadata/datasets?limit=30", default=[]))
    artifacts = get_json(api_base_url, "/metadata/artifacts?limit=30", default=[])
    history = get_json(api_base_url, "/metadata/history?limit=30", default=[])

    render_header(health)
    render_question_panel(api_base_url, datasets)
    render_result_area(api_base_url, datasets, artifacts, history)


def init_state() -> None:
    st.session_state.setdefault("api_base_url", DEFAULT_API_BASE_URL)
    st.session_state.setdefault("question_text", DEFAULT_QUESTION)
    st.session_state.setdefault("last_result", None)
    st.session_state.setdefault("upload_log", [])
    st.session_state.setdefault("selected_dataset_id", None)


def inject_css() -> None:
    st.markdown(
        """
        <style>
        :root {
            --di-border: #d8e1ec;
            --di-soft: #f6f9fc;
            --di-ink: #172033;
            --di-muted: #667085;
            --di-blue: #1f6feb;
            --di-green: #1f9d63;
            --di-warn: #b7791f;
        }
        .main .block-container {
            padding-top: 1rem;
            padding-bottom: 2rem;
            max-width: 1440px;
        }
        #MainMenu, footer {
            visibility: hidden;
            height: 0;
        }
        [data-testid="stHeader"] {
            background: transparent;
        }
        [data-testid="stSidebar"] {
            background: #f8fafc;
            border-right: 1px solid var(--di-border);
        }
        h1, h2, h3 {
            letter-spacing: 0;
        }
        .di-title {
            font-size: 1.45rem;
            font-weight: 780;
            color: var(--di-ink);
            line-height: 1.2;
            margin-bottom: 0.35rem;
        }
        .di-subtitle {
            color: var(--di-muted);
            font-size: 0.92rem;
            line-height: 1.45;
        }
        .di-topbar {
            padding: 0.35rem 0 0.4rem;
            margin-bottom: 0.55rem;
        }
        .di-status {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            padding: 0.42rem 0.65rem;
            border-radius: 999px;
            background: #ecfdf3;
            color: #027a48;
            border: 1px solid #abefc6;
            font-weight: 650;
            white-space: nowrap;
        }
        .di-status-bad {
            background: #fff4ed;
            color: #b42318;
            border-color: #fecdca;
        }
        .di-card {
            border: 1px solid var(--di-border);
            border-radius: 8px;
            background: white;
            padding: 1rem;
            height: 100%;
        }
        .di-card-title {
            color: var(--di-muted);
            font-size: 0.86rem;
            margin-bottom: 0.25rem;
        }
        .di-card-value {
            color: var(--di-ink);
            font-size: 1.45rem;
            font-weight: 760;
        }
        .di-section-title {
            font-size: 1.05rem;
            font-weight: 760;
            color: var(--di-ink);
            margin: 0.25rem 0 0.65rem;
        }
        .di-answer-box {
            border: 1px solid var(--di-border);
            background: #ffffff;
            border-radius: 8px;
            padding: 1rem 1.15rem;
        }
        .di-panel-title {
            font-weight: 760;
            color: var(--di-ink);
            margin-bottom: 0.65rem;
        }
        .di-file-row {
            border-top: 1px solid #edf2f7;
            padding: 0.65rem 0;
        }
        .di-file-name {
            font-weight: 680;
            color: var(--di-ink);
        }
        .di-file-meta {
            color: var(--di-muted);
            font-size: 0.82rem;
            margin-top: 0.08rem;
        }
        .di-ok-line {
            border: 1px solid #8ee1a8;
            background: #f0fff4;
            color: #087443;
            border-radius: 7px;
            padding: 0.62rem 0.75rem;
            margin-top: 0.7rem;
            font-weight: 650;
        }
        .di-soft-note {
            color: var(--di-muted);
            font-size: 0.85rem;
        }
        .di-report-section {
            border: 1px solid #edf2f7;
            border-radius: 8px;
            padding: 0.72rem 0.85rem;
            margin-top: 0.72rem;
            background: #fbfdff;
        }
        .di-report-heading {
            color: var(--di-ink);
            font-weight: 760;
            margin-bottom: 0.42rem;
        }
        .di-kv-row {
            display: grid;
            grid-template-columns: minmax(130px, 0.42fr) 1fr;
            border-bottom: 1px solid #edf2f7;
            padding: 0.48rem 0;
            gap: 0.8rem;
            align-items: start;
        }
        .di-kv-key {
            color: var(--di-muted);
            font-size: 0.86rem;
        }
        .di-kv-value {
            color: var(--di-ink);
            font-size: 0.9rem;
        }
        .di-tag {
            display: inline-block;
            border: 1px solid #c7d7fe;
            background: #eef4ff;
            color: #1849a9;
            border-radius: 999px;
            padding: 0.16rem 0.55rem;
            margin: 0.12rem 0.18rem 0.12rem 0;
            font-size: 0.82rem;
            font-weight: 650;
        }
        .di-good {
            border-color: #abefc6;
            background: #ecfdf3;
            color: #067647;
        }
        .di-warn {
            border-color: #fedf89;
            background: #fffaeb;
            color: #b54708;
        }
        .di-sidebar-footer {
            color: var(--di-muted);
            font-size: 0.82rem;
            padding-top: 1rem;
            margin-top: 1rem;
            border-top: 1px solid var(--di-border);
        }
        .stButton > button {
            border-radius: 7px;
            min-height: 2.25rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar() -> None:
    st.markdown('<div class="di-title">DataInsight-Agent</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="di-subtitle">企业文档与业务数据智能分析 Agent</div>',
        unsafe_allow_html=True,
    )
    with st.expander("后端设置", expanded=False):
        st.session_state.api_base_url = st.text_input(
            "后端 API 地址",
            value=st.session_state.api_base_url,
            help="默认连接本地 FastAPI 服务。",
        )
    api_base_url = st.session_state.api_base_url.rstrip("/")

    with st.container(border=True):
        st.markdown("#### 上传文档")
        st.caption("支持 PDF / TXT / Markdown")
        document_file = st.file_uploader(
            "拖拽文档到此处，或点击上传",
            type=["pdf", "txt", "md", "markdown"],
            key="document_uploader",
            label_visibility="collapsed",
        )
        if st.button("上传并索引文档", use_container_width=True, disabled=document_file is None):
            upload_file(api_base_url, "/upload/document", document_file, "document")

    with st.container(border=True):
        st.markdown("#### 上传数据")
        st.caption("支持 CSV / Excel")
        data_file = st.file_uploader(
            "拖拽数据到此处，或点击上传",
            type=["csv", "xlsx", "xls"],
            key="data_uploader",
            label_visibility="collapsed",
        )
        if st.button("上传并校验数据", use_container_width=True, disabled=data_file is None):
            upload_file(api_base_url, "/upload/data", data_file, "dataset")

    render_uploaded_files(api_base_url)

    with st.container(border=True):
        st.markdown("#### Energy Demo")
        if st.button("导入 Energy Demo 样例", use_container_width=True):
            import_energy_demo(api_base_url)

        for label, question in ENERGY_DEMO_QUESTIONS.items():
            if st.button(label, use_container_width=True):
                st.session_state.question_text = question
                st.session_state.quick_run = True
                st.rerun()

    st.markdown(f'<div class="di-sidebar-footer">{APP_VERSION}</div>', unsafe_allow_html=True)


def render_uploaded_files(api_base_url: str) -> None:
    st.markdown("#### 已上传文件")
    documents = unique_metadata_records(get_json(api_base_url, "/metadata/documents?limit=30", default=[]))
    datasets = unique_metadata_records(get_json(api_base_url, "/metadata/datasets?limit=30", default=[]))

    rows = []
    for item in documents:
        rows.append(
            {
                "文件名": item.get("filename"),
                "类型": f"文档 / {item.get('file_type') or '-'}",
                "大小": file_size_label(item.get("saved_path")),
                "状态": "已索引",
                "类别": "document",
            }
        )
    for item in datasets:
        rows.append(
            {
                "文件名": item.get("filename"),
                "类型": f"数据 / {item.get('file_type') or '-'}",
                "大小": file_size_label(item.get("saved_path")),
                "状态": "已校验",
                "类别": "dataset",
            }
        )

    if st.session_state.upload_log:
        for item in st.session_state.upload_log[-4:]:
            rows.append(
                {
                    "文件名": item["filename"],
                    "类型": item["kind"],
                    "大小": item["size"],
                    "状态": item["status"],
                    "类别": "document" if item["kind"] == "文档" else "dataset",
                }
            )

    rows = unique_uploaded_rows(rows)
    if rows:
        for row in rows[:6]:
            st.markdown(
                f"""
                <div class="di-file-row">
                    <div class="di-file-name">{html.escape(str(row["文件名"]))}</div>
                    <div class="di-file-meta">{html.escape(str(row["类型"]))} · {html.escape(str(row["大小"]))} · {html.escape(str(row["状态"]))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.caption("暂无上传记录。可先导入 Energy Demo 样例。")


def render_header(health: dict[str, Any] | None) -> None:
    is_ok = bool(health and health.get("status") == "ok")
    status_class = "di-status" if is_ok else "di-status di-status-bad"
    status_text = "服务运行中" if is_ok else "服务未连接"

    left, right = st.columns([0.78, 0.22])
    with left:
        st.markdown(
            f"""
            <div class="di-topbar">
              <div class="di-title">DataInsight-Agent 企业文档与业务数据智能分析 Agent</div>
              <div class="di-subtitle">{APP_VERSION} · 本地可运行 · Agentic RAG / Tools / SQLite Trace</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            f'<div style="text-align:right; padding-top:0.4rem;"><span class="{status_class}">{status_text}</span></div>',
            unsafe_allow_html=True,
        )

    if not is_ok:
        st.warning("未连接到 FastAPI 后端。请先启动后端服务，再刷新页面。")


def render_overview(
    documents: list[dict[str, Any]],
    datasets: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
    history: list[dict[str, Any]],
) -> None:
    cols = st.columns(4)
    metric_cards = [
        ("文档", len(documents), "已索引文档数"),
        ("数据集", len(datasets), "CSV / Excel 文件"),
        ("产物", len(artifacts), "图表与报告"),
        ("问答", len(history), "最近历史记录"),
    ]
    for col, (title, value, desc) in zip(cols, metric_cards, strict=False):
        with col:
            st.markdown(
                f"""
                <div class="di-card">
                  <div class="di-card-title">{html.escape(desc)}</div>
                  <div class="di-card-value">{value}</div>
                  <div class="di-subtitle">{html.escape(title)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_question_panel(api_base_url: str, datasets: list[dict[str, Any]]) -> None:
    with st.container(border=True):
        question = st.text_area(
            "请输入问题",
            key="question_text",
            height=118,
            placeholder=DEFAULT_QUESTION,
        )
        with st.expander("高级设置", expanded=False):
            dataset_options = {"自动选择最近数据集": None}
            for item in datasets:
                label = f"{item.get('filename')} ({str(item.get('id', ''))[:8]})"
                dataset_options[label] = item.get("id")

            selected_label = st.selectbox(
                "选择数据集",
                options=list(dataset_options.keys()),
                help="数据分析、图表和报告场景建议选择已上传的 CSV/Excel。",
            )
            st.session_state.selected_dataset_id = dataset_options[selected_label]

        run_from_quick_entry = st.session_state.pop("quick_run", False)
        hint_col, button_col = st.columns([0.78, 0.22])
        with hint_col:
            st.caption("Enter 发送，Shift + Enter 换行")
        with button_col:
            run_clicked = st.button("开始分析", type="primary", use_container_width=True)
        if run_clicked or run_from_quick_entry:
            run_agent_question(api_base_url, question, st.session_state.selected_dataset_id)


def render_result_area(
    api_base_url: str,
    datasets: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
    initial_history: list[dict[str, Any]],
) -> None:
    result = st.session_state.last_result
    if not result:
        st.info("请在上方输入问题并点击“开始分析”，或使用左侧 Energy Demo 快捷入口。")
        return

    tabs = st.tabs(["Agent 回答", "引用来源", "图表", "检索 Trace", "工具调用", "历史记录"])
    with tabs[0]:
        render_dashboard_tab(result, datasets, artifacts)
    with tabs[1]:
        render_citations_tab(result)
    with tabs[2]:
        render_chart_tab(result, datasets)
    with tabs[3]:
        render_trace_tab(result)
    with tabs[4]:
        render_tools_tab(result)
    with tabs[5]:
        history = get_json(api_base_url, "/metadata/history?limit=20", default=initial_history)
        render_history_tab(history)


def render_dashboard_tab(
    result: dict[str, Any],
    datasets: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> None:
    top_left, top_right = st.columns([0.48, 0.52])
    with top_left:
        with st.container(border=True):
            render_answer_panel(result)
    with top_right:
        with st.container(border=True):
            render_citation_panel(result)

    bottom_left, bottom_right = st.columns([0.48, 0.52])
    with bottom_left:
        with st.container(border=True):
            render_chart_panel(result, datasets, artifacts)
    with bottom_right:
        with st.container(border=True):
            render_trace_panel(result)


def render_answer_panel(result: dict[str, Any]) -> None:
    if result.get("route") == "report":
        render_report_panel(result)
        return

    st.markdown('<div class="di-panel-title">分析结论</div>', unsafe_allow_html=True)
    route = result.get("route", "unknown")
    sufficient = result.get("sufficient_context")
    status = "证据充分" if sufficient is True else "证据不足" if sufficient is False else "工具分析"
    status_class = "di-tag di-good" if sufficient is True else "di-tag di-warn"
    st.markdown(
        f"""
        <span class="di-tag">{html.escape(ROUTE_LABELS.get(route, route))}</span>
        <span class="{status_class}">{status}</span>
        """,
        unsafe_allow_html=True,
    )

    bullets = answer_to_bullets(result.get("final_answer") or result.get("answer"))
    if bullets:
        st.markdown("根据文档分析，当前结论可以概括为：")
        for item in bullets[:7]:
            st.markdown(f"- {item}")
    else:
        st.markdown(result.get("final_answer") or result.get("answer") or "暂无回答。")

    if result.get("citations"):
        st.markdown(
            '<div class="di-ok-line">结论综合了已检索文档内容，当前检索到相关引用。</div>',
            unsafe_allow_html=True,
        )
    elif result.get("uncertainty"):
        st.warning(result["uncertainty"])


def render_report_panel(result: dict[str, Any]) -> None:
    st.markdown('<div class="di-panel-title">结构化分析报告</div>', unsafe_allow_html=True)
    sufficient = result.get("sufficient_context")
    status = "证据充分" if sufficient is True else "证据不足" if sufficient is False else "综合分析"
    status_class = "di-tag di-good" if sufficient is True else "di-tag di-warn"
    st.markdown(
        f"""
        <span class="di-tag">报告生成</span>
        <span class="{status_class}">{status}</span>
        """,
        unsafe_allow_html=True,
    )

    answer = str(result.get("final_answer") or result.get("answer") or "")
    report_blocks = build_report_blocks(answer, result)
    for title, lines in report_blocks:
        st.markdown(
            f"""
            <div class="di-report-section">
              <div class="di-report-heading">{html.escape(title)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        for line in lines:
            st.markdown(f"- {line}")

    if answer:
        with st.expander("查看完整报告原文", expanded=False):
            st.markdown(answer)


def build_report_blocks(answer: str, result: dict[str, Any]) -> list[tuple[str, list[str]]]:
    evidence_section = markdown_section(answer, "文档依据")
    data_section = markdown_section(answer, "数据分析")
    conclusion_section = markdown_section(answer, "初步结论") or markdown_section(answer, "结论")

    citations = result.get("citations") or []
    citation_sources = sorted({item.get("source") for item in citations if item.get("source")})
    source_text = "、".join(citation_sources) if citation_sources else "当前报告未返回文档引用"

    blocks = [
        (
            "摘要",
            [
                shorten(
                    clean_markdown_text(conclusion_section)
                    or "本报告综合已上传文档、结构化数据和 Agent 工具调用结果，形成面向运行分析的初步结论。",
                    150,
                )
            ],
        ),
        ("数据发现", summarize_data_section(data_section)),
        (
            "文档依据",
            [
                f"引用来源：{source_text}",
                shorten(clean_markdown_text(evidence_section) or "当前报告依赖 Agentic RAG 返回的检索证据。", 150),
            ],
        ),
        ("运行建议", report_recommendations(answer)),
        ("不确定性说明", report_uncertainty(result)),
    ]
    return blocks


def summarize_data_section(section: str) -> list[str]:
    if not section:
        return ["当前报告未检测到明确的数据分析段落。"]

    row_match = re.search(r"['\"]row_count['\"]\s*:\s*(\d+)", section)
    columns_match = re.search(r"['\"]numeric_columns['\"]\s*:\s*\[([^\]]+)\]", section)
    rows = []
    if row_match:
        rows.append(f"样例数据共包含 {row_match.group(1)} 条记录。")
    if columns_match:
        columns = [
            item.strip(" '\"\n")
            for item in columns_match.group(1).split(",")
            if item.strip(" '\"\n")
        ]
        if columns:
            rows.append(f"可用于分析的数值字段包括：{', '.join(columns[:6])}。")

    cleaned = clean_markdown_text(section)
    if not rows and cleaned:
        rows.append(shorten(cleaned, 150))
    return rows or ["数据分析工具已完成运行，但当前摘要信息较少。"]


def report_recommendations(answer: str) -> list[str]:
    recommendation_section = markdown_section(answer, "建议")
    lines = answer_to_bullets(clean_markdown_text(recommendation_section))
    if lines:
        return lines[:3]
    return [
        "优先结合负荷、锅炉效率、排烟温度和 NOx 等指标做交叉分析。",
        "若效率下降且排烟温度升高，建议核查受热面积灰、漏风、配风方式和燃烧调整情况。",
        "后续应补充检修记录、燃料化验结果和现场运行日志，避免仅凭短周期数据过度判断。",
    ]


def report_uncertainty(result: dict[str, Any]) -> list[str]:
    if result.get("sufficient_context") is False:
        return ["当前检索链路判定证据不足，报告结论适合作为初步分析，不应直接替代现场诊断。"]
    if result.get("uncertainty"):
        return [str(result["uncertainty"])]
    return ["当前结论基于已上传样例文档和数据生成，真实业务中仍需结合更完整的运行日志和专家复核。"]


def markdown_section(text: str, keyword: str) -> str:
    lines = text.splitlines()
    capture = False
    captured: list[str] = []
    for line in lines:
        stripped = line.strip()
        is_heading = stripped.startswith("#")
        if is_heading and keyword in stripped:
            capture = True
            continue
        if capture and is_heading:
            break
        if capture:
            captured.append(line)
    return "\n".join(captured).strip()


def clean_markdown_text(text: str) -> str:
    cleaned_lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("[来源"):
            continue
        line = line.lstrip("#").strip()
        cleaned_lines.append(line)
    return " ".join(cleaned_lines).strip()


def render_citation_panel(result: dict[str, Any]) -> None:
    st.markdown('<div class="di-panel-title">引用来源</div>', unsafe_allow_html=True)
    rows = citation_rows(result)
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.caption("本次任务没有返回文档引用。")

    citations = result.get("citations") or []
    corpora = sorted({item.get("corpus") for item in citations if item.get("corpus")})
    corpus_text = "、".join(corpora) if corpora else "-"
    st.caption(f"相关文档：{len(citations)} 个    关联知识库：{corpus_text}")


def render_chart_panel(
    result: dict[str, Any],
    datasets: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> None:
    st.markdown('<div class="di-panel-title">负荷与锅炉效率趋势</div>', unsafe_allow_html=True)
    chart_path = resolve_chart_path(result, artifacts)
    if chart_path and Path(chart_path).exists():
        st.image(chart_path, caption="Agent 生成图表", use_container_width=True)
        st.caption(f"数据来源：{dataset_label(st.session_state.selected_dataset_id, datasets)}")
        return

    if ENERGY_DATA_PATH.exists():
        dataframe = pd.read_csv(ENERGY_DATA_PATH)
        chart_data = dataframe[["date", "load_mw", "boiler_efficiency_pct"]].set_index("date")
        st.line_chart(chart_data, use_container_width=True)
        st.caption("数据来源：examples/energy_demo/data/plant_daily.csv")
        return

    st.caption("暂无图表。可点击左侧“图表生成”快捷入口。")


def render_trace_panel(result: dict[str, Any]) -> None:
    st.markdown('<div class="di-panel-title">检索 Trace</div>', unsafe_allow_html=True)
    retrieval_rounds = result.get("retrieval_rounds") or []
    retrieved_chunks = result.get("retrieved_chunks") or []
    accepted_chunks = sum(int(item.get("accepted_count") or 0) for item in retrieval_rounds)
    top_k_values = [item.get("top_k") for item in retrieval_rounds if item.get("top_k") is not None]
    selected_corpora = result.get("selected_corpora") or []

    kv_rows = [
        ("retrieval_backend", result.get("retrieval_backend") or "-"),
        ("selected_corpora", tag_html(selected_corpora) if selected_corpora else "-"),
        ("rewritten_queries", str(len(result.get("rewritten_queries") or []))),
        ("retrieval_rounds", str(len(retrieval_rounds))),
        ("top_k", str(top_k_values[-1]) if top_k_values else "-"),
        ("sufficient_context", str(result.get("sufficient_context"))),
        ("retrieved_chunks", str(len(retrieved_chunks))),
        ("accepted_chunks", str(accepted_chunks)),
    ]
    st.markdown(
        "\n".join(
            f"""
            <div class="di-kv-row">
              <div class="di-kv-key">{html.escape(key)}</div>
              <div class="di-kv-value">{value}</div>
            </div>
            """
            for key, value in kv_rows
        ),
        unsafe_allow_html=True,
    )

    with st.expander("原始查询与重写查询", expanded=False):
        queries = result.get("rewritten_queries") or []
        if queries:
            for idx, query in enumerate(queries, start=1):
                st.markdown(f"{idx}. `{query}`")
        else:
            st.caption("本次没有 query rewrite。")


def render_answer_tab(result: dict[str, Any]) -> None:
    if result.get("route") == "report":
        render_report_panel(result)
        return

    st.markdown('<div class="di-section-title">分析结论</div>', unsafe_allow_html=True)
    route = result.get("route", "unknown")
    sufficient = result.get("sufficient_context")
    route_confidence = result.get("route_confidence")

    status = "证据充分" if sufficient is True else "证据不足" if sufficient is False else "非检索任务"
    status_class = "di-tag di-good" if sufficient is True else "di-tag di-warn"
    st.markdown(
        f"""
        <span class="di-tag">{html.escape(ROUTE_LABELS.get(route, route))}</span>
        <span class="{status_class}">{status}</span>
        <span class="di-tag">路由置信度：{format_number(route_confidence)}</span>
        """,
        unsafe_allow_html=True,
    )

    if result.get("citations"):
        st.success("结论综合了已检索文档内容，并在“引用来源”中列出依据。")

    answer = result.get("final_answer") or result.get("answer") or "暂无回答。"
    with st.container(border=True):
        st.markdown(answer)

    if result.get("uncertainty"):
        st.warning(result["uncertainty"])


def render_citations_tab(result: dict[str, Any]) -> None:
    retrieved_chunks = result.get("retrieved_chunks") or []
    rows = citation_rows(result)

    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("本次回答没有返回引用来源。数据分析或图表任务通常不会产生文档引用。")

    if retrieved_chunks:
        with st.expander("查看 retrieved_chunks 原始片段", expanded=False):
            st.json(retrieved_chunks)


def render_chart_tab(result: dict[str, Any], datasets: list[dict[str, Any]]) -> None:
    chart_path = result.get("chart_path") or (result.get("artifacts") or {}).get("chart_path")
    if chart_path and Path(chart_path).exists():
        st.image(chart_path, caption="Agent 生成图表", use_container_width=True)
        source = dataset_label(st.session_state.selected_dataset_id, datasets)
        st.caption(f"数据来源：{source}")
        return

    st.info("本次 Agent 没有生成图表。可使用左侧“图表生成”快捷入口。")


def render_trace_tab(result: dict[str, Any]) -> None:
    backend = result.get("retrieval_backend") or "无"
    selected_corpora = result.get("selected_corpora") or []
    rewritten_queries = result.get("rewritten_queries") or []
    retrieval_rounds = result.get("retrieval_rounds") or []
    retrieved_chunks = result.get("retrieved_chunks") or []

    top_cols = st.columns(3)
    top_cols[0].metric("retrieval_backend", backend)
    top_cols[1].metric("sufficient_context", str(result.get("sufficient_context")))
    top_cols[2].metric("latency_ms", result.get("latency_ms") or "-")

    st.markdown("**selected_corpora**")
    if selected_corpora:
        st.markdown(" ".join(f'<span class="di-tag">{html.escape(item)}</span>' for item in selected_corpora), unsafe_allow_html=True)
    else:
        st.caption("非 RAG 路径没有 selected_corpora。")

    st.markdown("**rewritten_queries**")
    if rewritten_queries:
        for idx, query in enumerate(rewritten_queries, start=1):
            st.markdown(f"{idx}. `{query}`")
    else:
        st.caption("本次没有 query rewrite。")

    if retrieval_rounds:
        st.markdown("**retrieval_rounds**")
        st.dataframe(pd.DataFrame(retrieval_rounds), use_container_width=True, hide_index=True)
        accepted = sum(int(item.get("accepted_count") or 0) for item in retrieval_rounds)
        st.caption(f"accepted_chunks：{accepted}")

    if retrieved_chunks:
        st.markdown("**retrieved_chunks**")
        chunk_rows = [
            {
                "label": item.get("label"),
                "source": item.get("source"),
                "corpus": item.get("corpus"),
                "score": format_number(item.get("score")),
                "text": shorten(item.get("text"), 160),
            }
            for item in retrieved_chunks
        ]
        st.dataframe(pd.DataFrame(chunk_rows), use_container_width=True, hide_index=True)


def render_tools_tab(result: dict[str, Any]) -> None:
    tool_calls = result.get("tool_calls") or []
    if not tool_calls:
        st.info("本次没有工具调用记录。")
        return

    rows = []
    for idx, call in enumerate(tool_calls, start=1):
        data = call.get("data") or {}
        rows.append(
            {
                "顺序": idx,
                "工具": TOOL_LABELS.get(call.get("tool_name"), call.get("tool_name")),
                "状态": "成功" if call.get("success") else "失败",
                "耗时": data.get("latency_ms") or result.get("latency_ms") or "-",
                "摘要": call.get("summary"),
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with st.expander("查看 tool_calls 原始结构", expanded=False):
        st.json(tool_calls)


def render_history_tab(history: list[dict[str, Any]]) -> None:
    if not history:
        st.info("暂无问答历史。")
        return

    rows = []
    for item in history:
        tool_names = [
            TOOL_LABELS.get(call.get("tool_name"), call.get("tool_name"))
            for call in item.get("tool_calls", [])
            if call.get("tool_name")
        ]
        rows.append(
            {
                "时间": format_local_time(item.get("created_at")),
                "问题": shorten(item.get("question"), 42),
                "回答摘要": shorten(item.get("answer"), 82),
                "路由": ROUTE_LABELS.get(item.get("route"), item.get("route")),
                "工具": " / ".join(tool_names) or "-",
                "耗时(ms)": item.get("latency_ms") or "-",
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def run_agent_question(api_base_url: str, question: str, dataset_id: str | None) -> None:
    if not question.strip():
        st.warning("请输入问题后再开始分析。")
        return

    payload = {"question": question.strip(), "top_k": 4}
    if dataset_id:
        payload["dataset_id"] = dataset_id

    with st.spinner("Agent 正在分析，请稍候..."):
        response = post_json(api_base_url, "/ask", payload, timeout=90)
    if response is None:
        return
    st.session_state.last_result = response


def upload_file(api_base_url: str, endpoint: str, uploaded_file: Any, kind: str) -> None:
    if uploaded_file is None:
        return

    file_bytes = uploaded_file.getvalue()
    files = {
        "file": (
            uploaded_file.name,
            file_bytes,
            uploaded_file.type or "application/octet-stream",
        )
    }
    with st.spinner("正在上传并处理文件..."):
        try:
            response = httpx.post(
                f"{api_base_url}{endpoint}",
                files=files,
                timeout=120,
                trust_env=False,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            st.error(f"上传失败：{exc}")
            return

    result = response.json()
    st.session_state.upload_log.append(
        {
            "filename": uploaded_file.name,
            "kind": "文档" if kind == "document" else "数据",
            "size": bytes_label(len(file_bytes)),
            "status": result.get("message", "上传成功"),
        }
    )
    st.success(result.get("message", "上传成功。"))
    st.rerun()


def import_energy_demo(api_base_url: str) -> None:
    imported = []
    if ENERGY_DOC_PATH.exists():
        imported.append(upload_local_file(api_base_url, "/upload/document", ENERGY_DOC_PATH, "text/markdown"))
    if ENERGY_DATA_PATH.exists():
        imported.append(upload_local_file(api_base_url, "/upload/data", ENERGY_DATA_PATH, "text/csv"))

    success_count = sum(1 for item in imported if item)
    if success_count == len(imported) and imported:
        st.success("Energy Demo 样例已导入。")
    elif imported:
        st.warning("Energy Demo 部分文件导入成功，请检查后端日志。")
    else:
        st.error("未找到 Energy Demo 样例文件。")
    st.rerun()


def upload_local_file(api_base_url: str, endpoint: str, path: Path, content_type: str) -> bool:
    try:
        file_bytes = path.read_bytes()
        files = {"file": (path.name, file_bytes, content_type)}
        response = httpx.post(
            f"{api_base_url}{endpoint}",
            files=files,
            timeout=120,
            trust_env=False,
        )
        response.raise_for_status()
        st.session_state.upload_log.append(
            {
                "filename": path.name,
                "kind": "文档" if endpoint.endswith("document") else "数据",
                "size": bytes_label(len(file_bytes)),
                "status": "Energy Demo 已导入",
            }
        )
        return True
    except httpx.HTTPError:
        return False


def get_json(api_base_url: str, endpoint: str, default: Any = None) -> Any:
    try:
        response = httpx.get(f"{api_base_url}{endpoint}", timeout=10, trust_env=False)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError:
        return default


def post_json(api_base_url: str, endpoint: str, payload: dict[str, Any], timeout: int = 60) -> Any:
    try:
        response = httpx.post(
            f"{api_base_url}{endpoint}",
            json=payload,
            timeout=timeout,
            trust_env=False,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        st.error(f"后端返回错误：{detail}")
    except httpx.HTTPError as exc:
        st.error(f"无法连接后端：{exc}")
    return None


def citation_rows(result: dict[str, Any]) -> list[dict[str, str]]:
    citations = result.get("citations") or []
    retrieved_chunks = result.get("retrieved_chunks") or []

    rows = []
    for index, item in enumerate(citations, start=1):
        rows.append(
            {
                "#": str(index),
                "来源文件": item.get("source") or "-",
                "章节/标题": item.get("label") or "-",
                "相关内容": shorten(item.get("preview"), 180),
                "置信度": format_number(item.get("score")),
            }
        )

    if not rows and retrieved_chunks:
        for index, item in enumerate(retrieved_chunks, start=1):
            rows.append(
                {
                    "#": str(index),
                    "来源文件": item.get("source") or "-",
                    "章节/标题": item.get("label") or first_line(item.get("text")),
                    "相关内容": shorten(item.get("text"), 180),
                    "置信度": format_number(item.get("score")),
                }
            )
    return rows


def answer_to_bullets(answer: Any) -> list[str]:
    text = "" if answer is None else str(answer)
    factors = extract_between(text, "通常受到", "等因素影响")
    if factors:
        return [
            item.strip(" ：:，。；;")
            for item in factors.replace("以及", "、").split("、")
            if item.strip(" ：:，。；;")
        ]

    lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("[来源"):
            continue
        if len(line) > 120:
            parts = [part.strip() for part in line.replace("；", "。").split("。") if part.strip()]
            lines.extend(parts)
        else:
            lines.append(line)
        if len(lines) >= 6:
            break
    return lines[:6]


def extract_between(text: str, start: str, end: str) -> str:
    start_index = text.find(start)
    if start_index < 0:
        return ""
    start_index += len(start)
    end_index = text.find(end, start_index)
    if end_index < 0:
        return ""
    return text[start_index:end_index]


def resolve_chart_path(result: dict[str, Any], artifacts: list[dict[str, Any]]) -> str | None:
    chart_path = result.get("chart_path") or (result.get("artifacts") or {}).get("chart_path")
    if chart_path:
        return str(chart_path)

    for item in artifacts:
        if item.get("artifact_type") == "chart" and item.get("file_path"):
            return str(item["file_path"])
    return None


def tag_html(values: list[str]) -> str:
    return " ".join(
        f'<span class="di-tag">{html.escape(str(value))}</span>' for value in values
    )


def unique_uploaded_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique_rows = []
    seen = set()
    for row in rows:
        key = (
            str(row.get("类别") or row.get("类型") or "").strip().lower(),
            str(row.get("文件名") or "").strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        unique_rows.append(row)
    return unique_rows


def unique_metadata_records(items: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    unique_items = []
    seen = set()
    for item in items or []:
        key = (
            str(item.get("filename") or "").strip().lower(),
            str(item.get("file_type") or "").strip().lower(),
            str(item.get("corpus") or "").strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        unique_items.append(item)
    return unique_items


def file_size_label(path_value: str | None) -> str:
    if not path_value:
        return "-"
    path = Path(path_value)
    if not path.exists():
        return "-"
    return bytes_label(path.stat().st_size)


def bytes_label(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.1f} MB"


def shorten(value: Any, limit: int = 120) -> str:
    text = "" if value is None else str(value).replace("\n", " ")
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}..."


def first_line(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    return text.splitlines()[0][:80] if text else "-"


def format_local_time(value: Any) -> str:
    if not value:
        return "-"
    try:
        text = str(value).replace("Z", "+00:00")
        timestamp = datetime.fromisoformat(text)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return timestamp.astimezone(LOCAL_TIMEZONE).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return str(value)


def format_number(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def dataset_label(dataset_id: str | None, datasets: list[dict[str, Any]]) -> str:
    if not dataset_id:
        return "自动选择最近上传数据集"
    for item in datasets:
        if item.get("id") == dataset_id:
            return item.get("filename") or dataset_id
    return dataset_id


if __name__ == "__main__":
    main()
