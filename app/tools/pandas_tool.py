import re

import pandas as pd

from app.tools.base import ToolResult


def run_pandas_analysis_tool(question: str, dataframe: pd.DataFrame) -> ToolResult:
    try:
        analysis = analyze_dataframe(question, dataframe)
        return ToolResult(
            tool_name="pandas_analysis",
            success=True,
            summary=analysis_to_text(analysis),
            data={"analysis": analysis},
            uncertainty="该结果由 pandas 基于已上传的本地数据集计算得到。",
        )
    except Exception as exc:
        return ToolResult(
            tool_name="pandas_analysis",
            success=False,
            summary=f"pandas 数据分析失败：{exc}",
            error=str(exc),
            uncertainty="请检查数据文件是否已上传，以及问题中指定的字段是否存在。",
        )


def analyze_dataframe(question: str, dataframe: pd.DataFrame) -> dict:
    lower_question = question.lower()
    numeric_columns = dataframe.select_dtypes(include="number").columns.tolist()
    matched_column = _match_column(question, dataframe.columns.tolist())

    if _has_any(lower_question, ["column", "columns", "字段", "列名"]):
        return {
            "operation": "columns",
            "columns": dataframe.columns.tolist(),
            "row_count": int(len(dataframe)),
        }

    if _has_any(lower_question, ["describe", "summary", "统计", "概览", "分布"]):
        return {
            "operation": "describe",
            "result": dataframe.describe(include="all").fillna("").to_dict(),
        }

    if _has_any(lower_question, ["average", "mean", "avg", "平均", "均值", "平均值"]):
        column = matched_column or _first_numeric(numeric_columns)
        return {
            "operation": "mean",
            "column": column,
            "value": None if column is None else float(dataframe[column].mean()),
        }

    if _has_any(lower_question, ["max", "maximum", "最高", "最大"]):
        column = matched_column or _first_numeric(numeric_columns)
        return {
            "operation": "max",
            "column": column,
            "value": None if column is None else float(dataframe[column].max()),
        }

    if _has_any(lower_question, ["min", "minimum", "最低", "最小"]):
        column = matched_column or _first_numeric(numeric_columns)
        return {
            "operation": "min",
            "column": column,
            "value": None if column is None else float(dataframe[column].min()),
        }

    if _has_any(lower_question, ["correlation", "corr", "相关"]):
        return {
            "operation": "correlation",
            "result": dataframe[numeric_columns].corr().round(4).fillna("").to_dict()
            if numeric_columns
            else {},
        }

    return {
        "operation": "basic_profile",
        "row_count": int(len(dataframe)),
        "columns": dataframe.columns.tolist(),
        "numeric_columns": numeric_columns,
        "preview": dataframe.head(5).fillna("").to_dict(orient="records"),
    }


def analysis_to_text(analysis: dict) -> str:
    operation = analysis.get("operation", "analysis")
    if operation in {"mean", "max", "min"}:
        operation_name = {"mean": "平均值", "max": "最大值", "min": "最小值"}[operation]
        return (
            f"分析类型：{operation_name}\n"
            f"分析字段：{analysis.get('column')}\n"
            f"计算结果：{analysis.get('value')}"
        )

    if operation == "columns":
        return (
            f"当前数据集共有 {analysis.get('row_count')} 行，字段包括："
            + ", ".join(analysis.get("columns", []))
        )

    if operation == "describe":
        return "已完成描述统计，详细结果见 analysis.result。"

    if operation == "correlation":
        return "已完成数值字段相关性分析，详细结果见 analysis.result。"

    return f"分析结果：\n{analysis}"


def _match_column(question: str, columns: list[str]) -> str | None:
    normalized_question = _normalize(question)
    for column in columns:
        normalized_column = _normalize(column)
        if normalized_column and normalized_column in normalized_question:
            return column

    words = set(re.findall(r"[a-z0-9_]+", normalized_question))
    for column in columns:
        column_words = set(re.findall(r"[a-z0-9_]+", _normalize(column)))
        if column_words and column_words.issubset(words):
            return column
    return None


def _normalize(value: str) -> str:
    return value.lower().replace("-", "_").replace(" ", "_")


def _first_numeric(columns: list[str]) -> str | None:
    return columns[0] if columns else None


def _has_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)
