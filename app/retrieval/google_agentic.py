from __future__ import annotations

import time

from app.core.config import get_settings
from app.retrieval.base import (
    BaseRetriever,
    RetrievalRequest,
    RetrievalResult,
    RetrievalRound,
)


class GoogleAgenticRagRetriever(BaseRetriever):
    """Optional adapter for Google Agentic RAG / Cross Corpus Retrieval.

    The project intentionally does not depend on Google Cloud packages yet.
    This adapter validates configuration and keeps the future integration point
    isolated from the rest of the Agent.
    """

    backend_name = "google_agentic_rag"

    def is_configured(self) -> bool:
        settings = get_settings()
        return all(
            [
                settings.google_cloud_project,
                settings.google_cloud_location,
                settings.google_rag_corpus_ids,
                settings.google_application_credentials,
            ]
        )

    def missing_config_fields(self) -> list[str]:
        settings = get_settings()
        missing = []
        if not settings.google_cloud_project:
            missing.append("GOOGLE_CLOUD_PROJECT")
        if not settings.google_cloud_location:
            missing.append("GOOGLE_CLOUD_LOCATION")
        if not settings.google_rag_corpus_ids:
            missing.append("GOOGLE_RAG_CORPUS_IDS")
        if not settings.google_application_credentials:
            missing.append("GOOGLE_APPLICATION_CREDENTIALS")
        return missing

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        started_at = time.perf_counter()
        settings = get_settings()
        corpus_ids = _parse_corpus_ids(settings.google_rag_corpus_ids)
        notice = (
            "Google Agentic RAG 配置已检测到，但当前项目只实现可选适配层；"
            "真实调用 Google RAG Engine / Cross Corpus Retrieval 的代码位置已预留，"
            "本地 demo 会继续回退到 local_agentic_rag。"
        )
        return RetrievalResult(
            answer=None,
            retrieval_backend=self.backend_name,
            selected_corpora=corpus_ids,
            rewritten_queries=[request.question],
            retrieval_rounds=[
                RetrievalRound(
                    round_index=1,
                    queries=[request.question],
                    corpora=corpus_ids,
                    top_k=request.top_k,
                    retrieved_count=0,
                    accepted_count=0,
                    sufficient_context=False,
                    notes=notice,
                )
            ],
            sufficient_context=False,
            citations=[],
            retrieved_chunks=[],
            used_llm=False,
            latency_ms=int((time.perf_counter() - started_at) * 1000),
            backend_notice=notice,
            metadata={
                "project": settings.google_cloud_project,
                "location": settings.google_cloud_location,
                "integration_method": "placeholder",
                "future_api": "AsyncRetrieveContexts / AskContexts",
            },
        )

    def _retrieve_from_google(self, request: RetrievalRequest) -> RetrievalResult:
        """Future Google Cloud call site.

        Planned integration:
        - initialize Vertex AI with GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION
        - build RagResource entries from GOOGLE_RAG_CORPUS_IDS
        - call Cross Corpus Retrieval, for example AsyncRetrieveContexts or AskContexts
        - map returned contexts to RetrievedChunk and RetrievalResult
        """
        raise NotImplementedError


def _parse_corpus_ids(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    return [item.strip() for item in raw_value.split(",") if item.strip()]
