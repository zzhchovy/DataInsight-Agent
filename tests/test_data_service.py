from app.tools.pandas_tool import analyze_dataframe
import pandas as pd


def test_analyze_dataframe_mean():
    dataframe = pd.DataFrame({"efficiency": [88.0, 89.0, 87.0]})
    result = analyze_dataframe("average efficiency", dataframe)
    assert result["operation"] == "mean"
    assert result["column"] == "efficiency"
    assert result["value"] == 88.0

