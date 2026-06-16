from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    app: str
    storage_dir: str


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    saved_path: str
    message: str


class DocumentUploadResponse(UploadResponse):
    chunks_added: int


class DatasetUploadResponse(UploadResponse):
    rows: int
    columns: list[str]


class DocumentMetadataRecord(BaseModel):
    id: str
    filename: str
    file_type: str | None = None
    corpus: str | None = None
    chunk_count: int
    saved_path: str | None = None
    created_at: str


class DatasetMetadataRecord(BaseModel):
    id: str
    filename: str
    file_type: str | None = None
    row_count: int
    columns: list[str] = Field(default_factory=list)
    saved_path: str | None = None
    created_at: str


class ArtifactMetadataRecord(BaseModel):
    id: str
    artifact_type: str
    file_path: str | None = None
    question: str | None = None
    route: str | None = None
    qa_id: str | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: str


class QaHistoryRecord(BaseModel):
    id: str
    question: str
    route: str | None = None
    answer: str | None = None
    retrieval_backend: str | None = None
    selected_corpora: list[str] = Field(default_factory=list)
    citations: list[dict] = Field(default_factory=list)
    tool_calls: list[dict] = Field(default_factory=list)
    latency_ms: int | None = None
    sufficient_context: bool | None = None
    dataset_id: str | None = None
    chart_path: str | None = None
    created_at: str


class AskRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        description="用户的自然语言问题。",
        examples=["根据文档，影响锅炉效率的因素有哪些？"],
    )
    dataset_id: str | None = Field(
        default=None,
        description="可选的数据集文件 ID。不填时默认使用最近上传的数据集。",
    )
    top_k: int = Field(
        default=4,
        ge=1,
        le=10,
        description="RAG 检索返回的文档片段数量。",
    )


class Citation(BaseModel):
    label: str | None = None
    source: str
    corpus: str | None = None
    chunk_index: int | None = None
    page: int | None = None
    score: float | None = None
    preview: str


class RetrievalRoundRecord(BaseModel):
    round_index: int
    queries: list[str] = Field(default_factory=list)
    corpora: list[str] = Field(default_factory=list)
    top_k: int
    retrieved_count: int
    accepted_count: int
    sufficient_context: bool
    notes: str | None = None


class RetrievedChunkRecord(BaseModel):
    label: str
    text: str
    source: str
    corpus: str
    chunk_index: int | None = None
    page: int | None = None
    score: float | None = None
    metadata: dict = Field(default_factory=dict)


class ToolCallRecord(BaseModel):
    tool_name: str
    success: bool
    summary: str
    data: dict = Field(default_factory=dict)
    artifacts: dict = Field(default_factory=dict)
    uncertainty: str | None = None
    error: str | None = None


class AskResponse(BaseModel):
    route: str
    router_reason: str | None = None
    route_confidence: float | None = None
    matched_keywords: list[str] = Field(default_factory=list)
    answer: str
    final_answer: str
    citations: list[Citation] = Field(default_factory=list)
    retrieval_backend: str | None = Field(
        default=None,
        examples=["local_agentic_rag"],
    )
    selected_corpora: list[str] = Field(
        default_factory=list,
        examples=[["energy_demo", "general_docs"]],
    )
    rewritten_queries: list[str] = Field(
        default_factory=list,
        examples=[
            [
                "根据文档，影响锅炉效率的因素有哪些？",
                "锅炉效率 燃烧质量 过量空气系数 排烟温度 受热面",
            ]
        ],
    )
    retrieval_rounds: list[RetrievalRoundRecord] = Field(default_factory=list)
    sufficient_context: bool | None = None
    retrieved_chunks: list[RetrievedChunkRecord] = Field(default_factory=list)
    used_llm: bool = False
    latency_ms: int | None = None
    backend_notice: str | None = None
    analysis: dict | None = None
    chart_path: str | None = None
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    artifacts: dict = Field(default_factory=dict)
    llm_used: bool = False
    llm_provider: str | None = None
    llm_model: str | None = None
    uncertainty: str | None = None
