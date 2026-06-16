# DataInsight-Agent 中文演示闭环

## 演示准备

启动服务：

```powershell
cd C:\Users\26976\Documents\DataInsight-Agent项目
& D:\codex\DataInsight-Agent\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开 Swagger：

```text
http://127.0.0.1:8000/docs
```

导入 energy demo：

```powershell
& D:\codex\DataInsight-Agent\.venv\Scripts\python.exe scripts\ingest_energy_demo.py
```

数据集 ID：

```text
energy_demo_plant_daily.csv
```

## Demo 1：文档问答

用户问题：

```text
根据文档，影响锅炉效率的因素有哪些？
```

调用路径：

```text
Router -> rag -> RetrievalService -> local_agentic_rag -> optional LLM fallback
```

重点输出：

- `retrieval_backend`: `local_agentic_rag`
- `selected_corpora`: 应包含 `energy_demo`
- `rewritten_queries`: 展示 query rewrite
- `retrieval_rounds`: 展示检索轮次
- `sufficient_context`: 展示证据是否足够
- `citations`: 展示引用来源

技术说明：

> 这个 demo 展示的是 Agentic RAG，不是简单 top-k 检索。系统会先改写 query，再选择 energy_demo corpus，检索后还会判断证据是否足够，并把整个 trace 返回。

## Demo 2：数据分析

用户问题：

```text
上传数据中 boiler_efficiency_pct 的平均值是多少？
```

调用路径：

```text
Router -> data -> pandas_analysis
```

重点输出：

- `route`: `data`
- `tool_calls`: `pandas_analysis`
- `analysis.operation`: `mean`
- `final_answer`: 平均值结果

技术说明：

> 对结构化数据，项目不让大模型猜数值，而是调用 pandas 做确定性计算。这样结果可复现，也更适合业务场景。

## Demo 3：图表生成

用户问题：

```text
画出 load_mw 和 boiler_efficiency_pct 的趋势图。
```

调用路径：

```text
Router -> chart -> chart_generation
```

重点输出：

- `route`: `chart`
- `chart_path`: 图表路径
- `artifacts.chart_path`: 图表产物
- `tool_calls`: `chart_generation`

技术说明：

> 这个 demo 说明 Agent 不只是文字问答，也能调用工具生成文件产物。图表路径会进入 artifacts，方便后续接前端展示。

## Demo 4：报告生成

用户问题：

```text
生成一份简短的运行分析报告。
```

调用路径：

```text
Router -> report -> RAG evidence + pandas analysis -> report_generation
```

重点输出：

- `route`: `report`
- `final_answer`: Markdown 报告
- `citations`: 文档依据
- `analysis`: 数据分析结果
- `retrieval_backend`: `local_agentic_rag`

技术说明：

> 报告 demo 展示的是综合任务，系统同时使用文档证据和结构化数据，最后生成结构化报告。这比单一 RAG 问答更接近真实业务分析。

## Demo 5：Google 后端回退

临时设置：

```powershell
$env:RETRIEVAL_BACKEND="google_agentic_rag"
```

用户问题：

```text
根据文档，影响锅炉效率的因素有哪些？
```

重点输出：

- `retrieval_backend`: `local_agentic_rag`
- `backend_notice`: Google Agentic RAG 未配置，已回退本地 Agentic RAG

技术说明：

> 我把 Google Cloud RAG 设计成可选扩展，而不是强依赖。没有云配置时系统不会崩溃，会自动回退本地模式，保证项目在任何电脑上都能演示。

演示后恢复：

```powershell
$env:RETRIEVAL_BACKEND="local_agentic_rag"
```
