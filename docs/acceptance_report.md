# DataInsight-Agent 双后端 Agentic RAG 功能验收报告

## 1. 新增文件

- `app/retrieval/__init__.py`
- `app/retrieval/base.py`
- `app/retrieval/local_agentic.py`
- `app/retrieval/google_agentic.py`
- `app/retrieval/service.py`
- `tests/test_retrieval_service.py`
- `scripts/eval_agentic_rag.py`
- `docs/acceptance_report.md`
- `docs/demo_guide.md`

## 2. 修改的核心文件

- `app/core/config.py`：新增 `RETRIEVAL_BACKEND` 和 Google RAG 配置项。
- `app/services/rag_service.py`：从直接调用向量库改为调用 `RetrievalService`。
- `app/services/report_service.py`：透传 RAG trace 到报告路径。
- `app/graph/state.py`：新增检索 trace 相关状态字段。
- `app/graph/workflow.py`：在 `tool_calls` 中记录检索后端、corpus、query rewrite 和 latency。
- `app/schemas.py`：`/ask` 响应新增 Agentic RAG trace 字段。
- `app/main.py`：更新 Swagger `/ask` 描述。
- `README.md`、`docs/architecture.md`、`docs/demo_guide.md`：补充双后端 Agentic RAG 说明。

## 3. local_agentic_rag 完整流程

默认后端是 `local_agentic_rag`，不依赖 Google Cloud，也不需要 API Key。

执行流程：

1. `query rewrite`：把用户问题改写成 2-3 个检索 query。
2. `corpus router`：根据问题选择 `general_docs`、`business_docs`、`data_dictionary`、`energy_demo`。
3. `iterative retrieval`：第一轮证据不足时扩大 top_k 和 corpus 范围。
4. `evidence checker`：判断 retrieved chunks 是否足以回答问题。
5. `retrieval trace`：返回 `selected_corpora`、`rewritten_queries`、`retrieval_rounds`、`sufficient_context`、`retrieved_chunks`。

## 4. google_agentic_rag 可选适配逻辑

`google_agentic_rag` 当前是可选适配层，不强依赖 Google Cloud SDK。

已实现：

- 配置项读取。
- 配置完整性检查。
- Google 真实调用方法位置预留。
- 未配置时自动回退本地后端。
- 在 `backend_notice` 中给出清晰提示。

需要的配置项：

```text
RETRIEVAL_BACKEND=google_agentic_rag
GOOGLE_CLOUD_PROJECT=...
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_RAG_CORPUS_IDS=...
GOOGLE_APPLICATION_CREDENTIALS=...
```

## 5. 没有 Google Cloud 配置时是否能自动回退

可以。

当设置 `RETRIEVAL_BACKEND=google_agentic_rag` 但缺少 Google 配置时，系统会：

1. 检测缺失字段。
2. 不抛异常。
3. 自动调用 `local_agentic_rag`。
4. 在响应中返回 `backend_notice`。

示例：

```text
retrieval_backend: local_agentic_rag
backend_notice: Google Agentic RAG 未配置，缺少：GOOGLE_CLOUD_PROJECT, GOOGLE_RAG_CORPUS_IDS, GOOGLE_APPLICATION_CREDENTIALS。已回退本地 Agentic RAG。
```

## 6. 当前 FastAPI /docs 中可演示接口

- `GET /health`：服务健康检查。
- `POST /upload/document`：上传并索引文档。
- `POST /upload/data`：上传 CSV / Excel。
- `GET /datasets`：查看已上传数据集。
- `GET /metadata/documents`：查看文档元数据。
- `GET /metadata/datasets`：查看数据集元数据。
- `GET /metadata/artifacts`：查看图表和报告产物元数据。
- `GET /metadata/history`：查看问答历史。
- `POST /ask`：统一 Agent 问答入口，可演示 RAG、数据分析、图表生成、报告生成和 Agentic RAG trace。

## 7. 三个中文问题测试示例

### 问题 1：文档问答

```text
根据文档，影响锅炉效率的因素有哪些？
```

实际验收重点：

- `route`: `rag`
- `retrieval_backend`: `local_agentic_rag`
- `selected_corpora`: `["energy_demo", "general_docs"]`
- `rewritten_queries`: 3 条
- `sufficient_context`: `true`
- `citations`: 1 条
- `tool_calls`: `["rag_retrieval"]`

### 问题 2：数据分析

```text
上传数据中 boiler_efficiency_pct 的平均值是多少？
```

实际验收重点：

- `route`: `data`
- `tool_calls`: 包含 `pandas_analysis`
- `analysis.operation`: `mean`
- `final_answer`: 包含计算结果

### 问题 3：报告生成

```text
生成一份简短的运行分析报告。
```

实际验收重点：

- `route`: `report`
- `retrieval_backend`: `local_agentic_rag`
- `selected_corpora`: 包含 `energy_demo`
- `citations`: 非空
- `final_answer`: Markdown 报告

## 8. 评测脚本验收结果

运行命令：

```powershell
& D:\codex\DataInsight-Agent\.venv\Scripts\python.exe scripts\eval_agentic_rag.py
```

当前结果：

```text
total_cases: 5
passed_cases: 5
pass_rate: 1.0
route_accuracy: 1.0
rag_recall_hit_rate: 1.0
citation_accuracy: 1.0
insufficient_evidence_handling_rate: 1.0
latency_ms_avg: 2.33
latency_ms_max: 3
```

评测报告输出：

```text
D:\codex\DataInsight-Agent\eval_reports\agentic_rag_eval.json
```

## 9. 当前风险和未完成项

- 本地 embedding 仍是哈希向量，语义召回能力有限。
- 本地 Agentic RAG 的 query rewrite、corpus router、evidence checker 是轻量规则版，不是 LLM planner。
- Google 后端目前只做适配层和配置检查，还没有真实调用 Google RAG Engine。
- SQLite 元数据管理已经补充为 MVP 版本，但还没有用户隔离、复杂检索和审计看板。
- 没有 Streamlit 前端截图，当前主要通过 Swagger 演示。
- 评测脚本是小规模 demo 评测，还不是系统化 benchmark。
