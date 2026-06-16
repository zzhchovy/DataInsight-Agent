from app.graph.router import classify_question, route_question


def test_route_rag_default():
    assert route_question("What factors affect boiler efficiency?") == "rag"


def test_route_data_average():
    assert route_question("What is the average efficiency?") == "data"


def test_route_chart():
    assert route_question("Draw a trend chart of load and efficiency.") == "chart"


def test_route_report():
    assert route_question("Generate a summary report.") == "report"


def test_route_chinese_rag():
    assert route_question("根据文档，影响锅炉效率的因素有哪些？") == "rag"


def test_route_chinese_data():
    assert route_question("上传数据中 boiler_efficiency_pct 的平均值是多少？") == "data"


def test_route_chinese_chart():
    assert route_question("画出 load_mw 和 boiler_efficiency_pct 的趋势图。") == "chart"


def test_route_chinese_report():
    assert route_question("生成一份简短的运行分析报告。") == "report"


def test_classify_question_returns_explainable_decision():
    decision = classify_question("画出 load_mw 和 boiler_efficiency_pct 的趋势图。")
    assert decision.route == "chart"
    assert decision.confidence > 0.7
    assert decision.matched_keywords
    assert "图表" in decision.reason or "趋势" in decision.reason
