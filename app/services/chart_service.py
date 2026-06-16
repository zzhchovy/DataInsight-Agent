from pathlib import Path
import uuid

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from app.core.paths import charts_dir
from app.tools.base import ToolResult
from app.tools.pandas_tool import _match_column


def run_chart_tool(question: str, dataframe: pd.DataFrame) -> ToolResult:
    try:
        result = _generate_chart_with_metadata(question, dataframe)
        return ToolResult(
            tool_name="chart_generation",
            success=True,
            summary=f"图表已生成：{result['chart_path']}",
            data={
                "x_column": result["x_column"],
                "y_columns": result["y_columns"],
            },
            artifacts={"chart_path": str(result["chart_path"])},
            uncertainty="当前图表工具使用简单规则选择字段，复杂需求建议在问题中明确指定列名。",
        )
    except Exception as exc:
        return ToolResult(
            tool_name="chart_generation",
            success=False,
            summary=f"图表生成失败：{exc}",
            error=str(exc),
            uncertainty="请确认数据中存在数值列，并在问题中说明希望绘制的字段。",
        )


def generate_chart(question: str, dataframe: pd.DataFrame) -> Path:
    return _generate_chart_with_metadata(question, dataframe)["chart_path"]


def _generate_chart_with_metadata(question: str, dataframe: pd.DataFrame) -> dict:
    numeric_columns = dataframe.select_dtypes(include="number").columns.tolist()
    if not numeric_columns:
        raise ValueError("No numeric columns available for chart generation.")

    requested_y = _match_column(question, numeric_columns)
    y_columns = [requested_y] if requested_y else numeric_columns[:2]
    x_column = _choose_x_column(dataframe)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    if x_column:
        x_values = dataframe[x_column]
        for column in y_columns:
            ax.plot(x_values, dataframe[column], marker="o", label=column)
        ax.set_xlabel(x_column)
    else:
        for column in y_columns:
            ax.plot(dataframe.index, dataframe[column], marker="o", label=column)
        ax.set_xlabel("index")

    ax.set_title("DataInsight-Agent Chart")
    ax.set_ylabel("value")
    ax.grid(True, alpha=0.3)
    ax.legend()
    fig.tight_layout()

    output_path = charts_dir() / f"chart_{uuid.uuid4().hex}.png"
    fig.savefig(output_path, dpi=160)
    plt.close(fig)
    return {
        "chart_path": output_path,
        "x_column": x_column,
        "y_columns": y_columns,
    }


def _choose_x_column(dataframe: pd.DataFrame) -> str | None:
    for column in dataframe.columns:
        if "date" in column.lower() or "time" in column.lower():
            return column
    return dataframe.columns[0] if len(dataframe.columns) else None
