from app.graph.workflow import run_agent
from app.tools.base import ToolResult


def test_data_route_returns_unified_agent_output(monkeypatch):
    import app.graph.workflow as workflow

    class FakeDataFrame:
        pass

    monkeypatch.setattr(workflow, "load_dataset", lambda dataset_id=None: FakeDataFrame())
    monkeypatch.setattr(
        workflow,
        "run_pandas_analysis_tool",
        lambda question, dataframe: ToolResult(
            tool_name="pandas_analysis",
            success=True,
            summary="分析类型：平均值\n分析字段：efficiency\n计算结果：88.0",
            data={"analysis": {"operation": "mean", "column": "efficiency", "value": 88.0}},
            uncertainty="测试不确定性说明。",
        ),
    )

    state = run_agent("上传数据中 efficiency 的平均值是多少？", dataset_id="demo.csv")

    assert state["route"] == "data"
    assert state["router_reason"]
    assert state["route_confidence"] > 0
    assert state["final_answer"] == state["answer"]
    assert state["tool_calls"][0]["tool_name"] == "pandas_analysis"
    assert state["analysis"]["value"] == 88.0


def test_chart_route_returns_artifacts(monkeypatch):
    import app.graph.workflow as workflow

    class FakeDataFrame:
        pass

    monkeypatch.setattr(workflow, "load_dataset", lambda dataset_id=None: FakeDataFrame())
    monkeypatch.setattr(
        workflow,
        "run_chart_tool",
        lambda question, dataframe: ToolResult(
            tool_name="chart_generation",
            success=True,
            summary="图表已生成：D:/demo/chart.png",
            artifacts={"chart_path": "D:/demo/chart.png"},
            data={"x_column": "date", "y_columns": ["efficiency"]},
            uncertainty="测试图表说明。",
        ),
    )

    state = run_agent("画出 efficiency 的趋势图。", dataset_id="demo.csv")

    assert state["route"] == "chart"
    assert state["chart_path"] == "D:/demo/chart.png"
    assert state["artifacts"]["chart_path"] == "D:/demo/chart.png"
    assert state["tool_calls"][0]["tool_name"] == "chart_generation"
