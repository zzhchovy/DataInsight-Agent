from pathlib import Path
import shutil
import uuid

from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from app.core.config import get_settings
from app.core.paths import document_uploads_dir, ensure_storage_dirs
from app.graph.workflow import run_agent
from app.schemas import (
    AskRequest,
    AskResponse,
    ArtifactMetadataRecord,
    DatasetMetadataRecord,
    DatasetUploadResponse,
    DocumentMetadataRecord,
    DocumentUploadResponse,
    HealthResponse,
    QaHistoryRecord,
)
from app.retrieval.local_agentic import infer_corpus
from app.services.data_service import list_datasets, save_data_upload
from app.services.document_loader import load_document
from app.services.metadata_store import (
    init_metadata_db,
    list_artifacts,
    list_datasets_metadata,
    list_documents,
    list_qa_history,
    record_agent_run,
    record_dataset,
    record_document,
)
from app.services.text_splitter import split_documents
from app.services.vector_store import VectorStore


app = FastAPI(
    title="DataInsight-Agent",
    description="企业文档与业务数据智能分析 Agent MVP。支持文档 RAG、CSV/Excel 分析、图表生成和结构化报告。",
    version="0.1.0",
)


@app.on_event("startup")
def on_startup() -> None:
    ensure_storage_dirs()
    init_metadata_db()


@app.get("/health", response_model=HealthResponse, summary="健康检查")
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        storage_dir=str(settings.storage_dir),
    )


@app.post(
    "/upload/document",
    response_model=DocumentUploadResponse,
    summary="上传并索引文档",
    description="上传 PDF / TXT / Markdown 文档，系统会解析文本、切分片段，并写入本地向量库。",
)
def upload_document(file: UploadFile = File(...)) -> DocumentUploadResponse:
    ensure_storage_dirs()
    original_name = file.filename or "document.txt"
    suffix = Path(original_name).suffix.lower()
    file_id = f"{uuid.uuid4().hex}{suffix}"
    saved_path = document_uploads_dir() / file_id

    try:
        with saved_path.open("wb") as output:
            shutil.copyfileobj(file.file, output)

        documents = load_document(saved_path, source_name=original_name)
        chunks = split_documents(documents)
        chunks_added = VectorStore().add_chunks(chunks)
        record_document(
            file_id=file_id,
            filename=original_name,
            file_type=suffix.lstrip(".") or None,
            corpus=infer_corpus(original_name),
            chunk_count=chunks_added,
            saved_path=str(saved_path),
        )
        return DocumentUploadResponse(
            file_id=file_id,
            filename=original_name,
            saved_path=str(saved_path),
            chunks_added=chunks_added,
            message="文档已上传、解析、切分并写入知识库。",
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post(
    "/upload/data",
    response_model=DatasetUploadResponse,
    summary="上传业务数据",
    description="上传 CSV / Excel 数据，系统会保存文件并用 pandas 读取校验。",
)
def upload_data(file: UploadFile = File(...)) -> DatasetUploadResponse:
    ensure_storage_dirs()
    try:
        dataset_id, saved_path, dataframe = save_data_upload(file)
        record_dataset(
            dataset_id=dataset_id,
            filename=file.filename or dataset_id,
            file_type=Path(file.filename or dataset_id).suffix.lower().lstrip(".") or None,
            row_count=int(len(dataframe)),
            columns=[str(column) for column in dataframe.columns.tolist()],
            saved_path=str(saved_path),
        )
        return DatasetUploadResponse(
            file_id=dataset_id,
            filename=file.filename or dataset_id,
            saved_path=str(saved_path),
            rows=int(len(dataframe)),
            columns=dataframe.columns.tolist(),
            message="数据文件已上传并通过读取校验。",
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/datasets", summary="查看已上传数据集")
def datasets() -> list[dict]:
    ensure_storage_dirs()
    return list_datasets()


@app.get(
    "/metadata/documents",
    response_model=list[DocumentMetadataRecord],
    summary="查看文档元数据",
)
def metadata_documents(
    limit: int = Query(default=100, ge=1, le=500, description="最多返回多少条记录。")
) -> list[dict]:
    ensure_storage_dirs()
    return list_documents(limit=limit)


@app.get(
    "/metadata/datasets",
    response_model=list[DatasetMetadataRecord],
    summary="查看数据集元数据",
)
def metadata_datasets(
    limit: int = Query(default=100, ge=1, le=500, description="最多返回多少条记录。")
) -> list[dict]:
    ensure_storage_dirs()
    return list_datasets_metadata(limit=limit)


@app.get(
    "/metadata/artifacts",
    response_model=list[ArtifactMetadataRecord],
    summary="查看图表和报告产物元数据",
)
def metadata_artifacts(
    limit: int = Query(default=100, ge=1, le=500, description="最多返回多少条记录。")
) -> list[dict]:
    ensure_storage_dirs()
    return list_artifacts(limit=limit)


@app.get(
    "/metadata/history",
    response_model=list[QaHistoryRecord],
    summary="查看问答历史",
)
def metadata_history(
    limit: int = Query(default=100, ge=1, le=500, description="最多返回多少条记录。")
) -> list[dict]:
    ensure_storage_dirs()
    return list_qa_history(limit=limit)


@app.post(
    "/ask",
    response_model=AskResponse,
    summary="向 Agent 提问",
    description=(
        "输入自然语言问题，Agent 会判断走 RAG、数据分析、图表生成还是报告生成。"
        "RAG 路径会返回 Agentic RAG trace，包括 retrieval_backend、selected_corpora、"
        "rewritten_queries、retrieval_rounds、sufficient_context 和 retrieved_chunks。"
    ),
)
def ask(request: AskRequest) -> AskResponse:
    ensure_storage_dirs()
    state = run_agent(
        question=request.question,
        dataset_id=request.dataset_id,
        top_k=request.top_k,
    )
    record_agent_run(request.question, request.dataset_id, state)
    return AskResponse(
        route=state.get("route", "unknown"),
        router_reason=state.get("router_reason"),
        route_confidence=state.get("route_confidence"),
        matched_keywords=state.get("matched_keywords", []),
        answer=state.get("answer", ""),
        final_answer=state.get("final_answer", state.get("answer", "")),
        citations=state.get("citations", []),
        retrieval_backend=state.get("retrieval_backend"),
        selected_corpora=state.get("selected_corpora", []),
        rewritten_queries=state.get("rewritten_queries", []),
        retrieval_rounds=state.get("retrieval_rounds", []),
        sufficient_context=state.get("sufficient_context"),
        retrieved_chunks=state.get("retrieved_chunks", []),
        used_llm=state.get("used_llm", state.get("llm_used", False)),
        latency_ms=state.get("latency_ms"),
        backend_notice=state.get("backend_notice"),
        analysis=state.get("analysis"),
        chart_path=state.get("chart_path"),
        tool_calls=state.get("tool_calls", []),
        artifacts=state.get("artifacts", {}),
        llm_used=state.get("llm_used", False),
        llm_provider=state.get("llm_provider"),
        llm_model=state.get("llm_model"),
        uncertainty=state.get("uncertainty"),
    )
