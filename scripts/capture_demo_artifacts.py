import json
import os
import shutil
from pathlib import Path
import sys
import textwrap
from typing import Any

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings
from app.core.paths import storage_root
from app.main import app
from scripts.ingest_energy_demo import DEMO_DATASET_ID, main as ingest_energy_demo


ARTIFACT_ROOT = storage_root() / "demo_artifacts"
RESPONSES_DIR = ARTIFACT_ROOT / "responses"
SCREENSHOTS_DIR = ARTIFACT_ROOT / "screenshots"
REPORTS_DIR = ARTIFACT_ROOT / "reports"


DEMO_CASES = [
    {
        "id": "demo_1_rag",
        "title": "Demo 1 - 文档问答 / Agentic RAG",
        "question": "根据文档，影响锅炉效率的因素有哪些？",
    },
    {
        "id": "demo_2_data",
        "title": "Demo 2 - 数据分析 / pandas 工具",
        "question": "上传数据中 boiler_efficiency_pct 的平均值是多少？",
    },
    {
        "id": "demo_3_chart",
        "title": "Demo 3 - 图表生成 / chart 工具",
        "question": "画出 load_mw 和 boiler_efficiency_pct 的趋势图。",
    },
    {
        "id": "demo_4_report",
        "title": "Demo 4 - 报告生成 / report 节点",
        "question": "生成一份简短的运行分析报告。",
    },
    {
        "id": "demo_5_google_fallback",
        "title": "Demo 5 - Google 后端未配置自动回退",
        "question": "根据文档，影响锅炉效率的因素有哪些？",
        "force_google_backend": True,
    },
]


def main() -> None:
    prepare_dirs()
    ingest_energy_demo()
    client = TestClient(app)

    summaries = []
    for case in DEMO_CASES:
        payload = run_case(client, case)
        response_path = RESPONSES_DIR / f"{case['id']}_response.json"
        response_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        screenshot_path = SCREENSHOTS_DIR / f"{case['id']}_swagger_response.png"
        render_response_screenshot(case=case, payload=payload, output_path=screenshot_path)

        copied_chart_path = None
        if case["id"] == "demo_3_chart" and payload.get("chart_path"):
            source_chart = Path(payload["chart_path"])
            if source_chart.exists():
                copied_chart_path = SCREENSHOTS_DIR / "demo_3_chart_output.png"
                shutil.copyfile(source_chart, copied_chart_path)

        report_path = None
        report_screenshot_path = None
        if case["id"] == "demo_4_report":
            report_path = REPORTS_DIR / "demo_4_report_output.md"
            report_path.write_text(payload.get("final_answer", ""), encoding="utf-8")
            report_screenshot_path = SCREENSHOTS_DIR / "demo_4_report_output.png"
            render_text_screenshot(
                title="Demo 4 - 运行分析报告输出",
                text=payload.get("final_answer", ""),
                output_path=report_screenshot_path,
            )

        summaries.append(
            {
                "id": case["id"],
                "title": case["title"],
                "question": case["question"],
                "route": payload.get("route"),
                "retrieval_backend": payload.get("retrieval_backend"),
                "selected_corpora": payload.get("selected_corpora", []),
                "rewritten_queries_count": len(payload.get("rewritten_queries", [])),
                "sufficient_context": payload.get("sufficient_context"),
                "citations_count": len(payload.get("citations", [])),
                "chart_path": str(copied_chart_path) if copied_chart_path else None,
                "response_json": str(response_path),
                "response_screenshot": str(screenshot_path),
                "report_output": str(report_path) if report_path else None,
                "report_screenshot": str(report_screenshot_path) if report_screenshot_path else None,
            }
        )

    summary_path = ARTIFACT_ROOT / "demo_artifacts_summary.md"
    summary_path.write_text(build_summary_markdown(summaries), encoding="utf-8")
    print(f"Demo artifacts saved to: {ARTIFACT_ROOT}")
    print(f"Summary: {summary_path}")


def prepare_dirs() -> None:
    for path in [ARTIFACT_ROOT, RESPONSES_DIR, SCREENSHOTS_DIR, REPORTS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def run_case(client: TestClient, case: dict[str, Any]) -> dict[str, Any]:
    if case.get("force_google_backend"):
        os.environ["RETRIEVAL_BACKEND"] = "google_agentic_rag"
        os.environ.pop("GOOGLE_CLOUD_PROJECT", None)
        os.environ.pop("GOOGLE_RAG_CORPUS_IDS", None)
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
        get_settings.cache_clear()
    else:
        os.environ["RETRIEVAL_BACKEND"] = "local_agentic_rag"
        get_settings.cache_clear()

    response = client.post(
        "/ask",
        json={
            "question": case["question"],
            "dataset_id": DEMO_DATASET_ID,
            "top_k": 4,
        },
    )
    response.raise_for_status()
    payload = response.json()

    os.environ["RETRIEVAL_BACKEND"] = "local_agentic_rag"
    get_settings.cache_clear()
    return payload


def render_response_screenshot(
    case: dict[str, Any],
    payload: dict[str, Any],
    output_path: Path,
) -> None:
    important_payload = {
        "route": payload.get("route"),
        "router_reason": payload.get("router_reason"),
        "retrieval_backend": payload.get("retrieval_backend"),
        "selected_corpora": payload.get("selected_corpora"),
        "rewritten_queries": payload.get("rewritten_queries"),
        "retrieval_rounds": payload.get("retrieval_rounds"),
        "sufficient_context": payload.get("sufficient_context"),
        "citations_count": len(payload.get("citations", [])),
        "chart_path": payload.get("chart_path"),
        "backend_notice": payload.get("backend_notice"),
        "final_answer_preview": payload.get("final_answer", "")[:700],
    }
    text = (
        f"POST /ask\n"
        f"Question: {case['question']}\n\n"
        + json.dumps(important_payload, ensure_ascii=False, indent=2)
    )
    render_text_screenshot(case["title"], text, output_path)


def render_text_screenshot(title: str, text: str, output_path: Path) -> None:
    title_font = load_font(size=28, bold=True)
    body_font = load_font(size=18, bold=False)
    width = 1280
    margin = 42
    line_spacing = 8

    wrapped_lines = []
    for raw_line in text.splitlines():
        if not raw_line:
            wrapped_lines.append("")
            continue
        wrapped_lines.extend(textwrap.wrap(raw_line, width=88) or [""])

    title_height = 42
    line_height = 28
    height = max(720, margin * 2 + title_height + len(wrapped_lines) * (line_height + line_spacing))

    image = Image.new("RGB", (width, height), color=(246, 248, 250))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        [24, 24, width - 24, height - 24],
        radius=18,
        fill=(255, 255, 255),
        outline=(208, 215, 222),
        width=2,
    )
    draw.text((margin, margin), title, fill=(17, 24, 39), font=title_font)

    y = margin + title_height + 22
    for line in wrapped_lines:
        draw.text((margin, y), line, fill=(36, 41, 47), font=body_font)
        y += line_height + line_spacing

    image.save(output_path)


def load_font(size: int, bold: bool) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path(r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\simsun.ttc"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def build_summary_markdown(summaries: list[dict[str, Any]]) -> str:
    lines = [
        "# DataInsight-Agent Demo Artifacts",
        "",
        "本目录保存按 `docs/demo_guide.md` 真实运行 5 个 demo 后生成的响应、截图、图表和报告产物。",
        "",
    ]
    for item in summaries:
        lines.extend(
            [
                f"## {item['title']}",
                "",
                f"- 用户问题：{item['question']}",
                f"- route：`{item['route']}`",
                f"- retrieval_backend：`{item['retrieval_backend']}`",
                f"- selected_corpora：`{item['selected_corpora']}`",
                f"- rewritten_queries_count：`{item['rewritten_queries_count']}`",
                f"- sufficient_context：`{item['sufficient_context']}`",
                f"- citations_count：`{item['citations_count']}`",
                f"- 响应 JSON：`{item['response_json']}`",
                f"- Swagger 响应截图：`{item['response_screenshot']}`",
            ]
        )
        if item.get("chart_path"):
            lines.append(f"- 图表截图：`{item['chart_path']}`")
        if item.get("report_output"):
            lines.append(f"- 报告 Markdown：`{item['report_output']}`")
        if item.get("report_screenshot"):
            lines.append(f"- 报告截图：`{item['report_screenshot']}`")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
