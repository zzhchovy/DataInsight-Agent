from __future__ import annotations

from dataclasses import dataclass
import re
import time

from app.retrieval.base import (
    BaseRetriever,
    RetrievalRequest,
    RetrievalResult,
    RetrievalRound,
    RetrievedChunk,
)
from app.services.vector_store import RetrievalHit, VectorStore


CORPUS_KEYWORDS = {
    "energy_demo": [
        "energy",
        "boiler",
        "efficiency",
        "load_mw",
        "coal",
        "nox",
        "锅炉",
        "效率",
        "负荷",
        "煤耗",
        "排烟",
        "能源",
        "机组",
    ],
    "data_dictionary": [
        "schema",
        "dictionary",
        "字段",
        "列名",
        "数据字典",
        "表结构",
    ],
    "business_docs": [
        "business",
        "kpi",
        "metric",
        "report",
        "业务",
        "指标",
        "报表",
        "经营",
    ],
    "general_docs": [
        "document",
        "policy",
        "manual",
        "文档",
        "资料",
        "说明",
    ],
}

ALL_CORPORA = ["general_docs", "business_docs", "data_dictionary", "energy_demo"]


@dataclass(frozen=True)
class EvidenceCheck:
    sufficient: bool
    reason: str


class LocalAgenticRagRetriever(BaseRetriever):
    backend_name = "local_agentic_rag"

    def __init__(self, vector_store: VectorStore | None = None):
        self.vector_store = vector_store or VectorStore()

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        started_at = time.perf_counter()
        rewritten_queries = rewrite_query(request.question)
        selected_corpora = route_corpora(request.question)

        accepted_hits: list[RetrievalHit] = []
        retrieval_rounds: list[RetrievalRound] = []

        round_one_hits = self._retrieve_round(
            rewritten_queries=rewritten_queries,
            selected_corpora=selected_corpora,
            top_k=request.top_k,
        )
        accepted_hits = _dedupe_hits(round_one_hits)
        check = check_evidence(request.question, accepted_hits)
        retrieval_rounds.append(
            RetrievalRound(
                round_index=1,
                queries=rewritten_queries,
                corpora=selected_corpora,
                top_k=request.top_k,
                retrieved_count=len(round_one_hits),
                accepted_count=len(accepted_hits),
                sufficient_context=check.sufficient,
                notes=check.reason,
            )
        )

        if not check.sufficient:
            expanded_corpora = expand_corpora(selected_corpora)
            expanded_top_k = max(request.top_k * 2, request.top_k + 2)
            round_two_hits = self._retrieve_round(
                rewritten_queries=rewritten_queries,
                selected_corpora=expanded_corpora,
                top_k=expanded_top_k,
            )
            accepted_hits = _dedupe_hits([*accepted_hits, *round_two_hits])
            check = check_evidence(request.question, accepted_hits)
            retrieval_rounds.append(
                RetrievalRound(
                    round_index=2,
                    queries=rewritten_queries,
                    corpora=expanded_corpora,
                    top_k=expanded_top_k,
                    retrieved_count=len(round_two_hits),
                    accepted_count=len(accepted_hits),
                    sufficient_context=check.sufficient,
                    notes=check.reason,
                )
            )
            selected_corpora = expanded_corpora

        chunks = [
            _hit_to_chunk(hit, index)
            for index, hit in enumerate(accepted_hits[: max(1, request.top_k)], start=1)
        ]
        citations = [_chunk_to_citation(chunk) for chunk in chunks]
        latency_ms = int((time.perf_counter() - started_at) * 1000)

        return RetrievalResult(
            answer=None,
            retrieval_backend=self.backend_name,
            selected_corpora=selected_corpora,
            rewritten_queries=rewritten_queries,
            retrieval_rounds=retrieval_rounds,
            sufficient_context=check.sufficient,
            citations=citations,
            retrieved_chunks=chunks,
            used_llm=False,
            latency_ms=latency_ms,
        )

    def _retrieve_round(
        self,
        rewritten_queries: list[str],
        selected_corpora: list[str],
        top_k: int,
    ) -> list[RetrievalHit]:
        hits: list[RetrievalHit] = []
        search_top_k = max(top_k * 4, top_k)
        for query in rewritten_queries:
            query_hits = self.vector_store.query(query, top_k=search_top_k)
            filtered_hits = [
                hit for hit in query_hits if infer_corpus(hit.source) in selected_corpora
            ]
            hits.extend(filtered_hits or query_hits[:top_k])
        return hits


def rewrite_query(question: str) -> list[str]:
    normalized = " ".join(question.strip().split())
    queries = [normalized]

    if _has_any(normalized.lower(), ["factor", "cause", "influence", "影响", "因素", "原因"]):
        queries.append(f"{normalized} 影响因素 原因 机制")

    if _has_any(normalized.lower(), ["efficiency", "boiler", "效率", "锅炉"]):
        queries.append("锅炉效率 燃烧质量 过量空气系数 排烟温度 受热面")

    if _has_any(normalized.lower(), ["字段", "列名", "schema", "dictionary"]):
        queries.append(f"{normalized} 字段 含义 数据字典")

    if len(queries) == 1:
        queries.append(f"{normalized} 相关资料 依据")

    return _unique(queries)[:3]


def route_corpora(question: str) -> list[str]:
    lowered = question.lower()
    selected = []
    for corpus, keywords in CORPUS_KEYWORDS.items():
        if _has_any(lowered, keywords):
            selected.append(corpus)

    if not selected:
        selected.append("general_docs")

    return _unique(selected)


def expand_corpora(selected_corpora: list[str]) -> list[str]:
    expanded = [*selected_corpora]
    for corpus in ["general_docs", "energy_demo", "business_docs", "data_dictionary"]:
        if corpus not in expanded:
            expanded.append(corpus)
    return expanded


def check_evidence(question: str, hits: list[RetrievalHit]) -> EvidenceCheck:
    if not hits:
        return EvidenceCheck(False, "没有检索到可用片段。")

    question_tokens = set(_tokens(question))
    evidence_text = " ".join(hit.text[:800] for hit in hits)
    evidence_tokens = set(_tokens(evidence_text))
    overlap = question_tokens & evidence_tokens

    if len(hits) >= 2 and len(overlap) >= 2:
        return EvidenceCheck(True, "检索到多个片段，且与问题存在足够关键词重合。")

    if len(overlap) >= 3:
        return EvidenceCheck(True, "检索片段与问题存在较高关键词重合。")

    energy_question = _has_any(question.lower(), CORPUS_KEYWORDS["energy_demo"])
    if energy_question and any(keyword in evidence_text for keyword in ["锅炉效率", "排烟温度", "过量空气"]):
        return EvidenceCheck(True, "检索片段包含领域核心证据。")

    return EvidenceCheck(False, "检索片段数量或关键词重合不足，已尝试扩大检索范围。")


def infer_corpus(source: str) -> str:
    lowered = source.lower()
    if _has_any(lowered, CORPUS_KEYWORDS["energy_demo"]):
        return "energy_demo"
    if _has_any(lowered, CORPUS_KEYWORDS["data_dictionary"]):
        return "data_dictionary"
    if _has_any(lowered, CORPUS_KEYWORDS["business_docs"]):
        return "business_docs"
    return "general_docs"


def _hit_to_chunk(hit: RetrievalHit, index: int) -> RetrievedChunk:
    return RetrievedChunk(
        label=f"来源{index}",
        text=hit.text,
        source=hit.source,
        corpus=infer_corpus(hit.source),
        chunk_index=hit.chunk_index,
        page=hit.page,
        score=hit.score,
    )


def _chunk_to_citation(chunk: RetrievedChunk) -> dict:
    return {
        "label": chunk.label,
        "source": chunk.source,
        "corpus": chunk.corpus,
        "chunk_index": chunk.chunk_index,
        "page": chunk.page,
        "score": chunk.score,
        "preview": chunk.text[:240],
    }


def _dedupe_hits(hits: list[RetrievalHit]) -> list[RetrievalHit]:
    seen = set()
    unique_hits = []
    for hit in hits:
        key = (hit.source, hit.chunk_index, hit.text[:120])
        if key in seen:
            continue
        seen.add(key)
        unique_hits.append(hit)
    return unique_hits


def _tokens(text: str) -> list[str]:
    lowered = text.lower()
    ascii_tokens = re.findall(r"[a-z0-9_]+", lowered)
    cjk_terms = re.findall(r"[\u4e00-\u9fff]{2,}", lowered)
    return ascii_tokens + cjk_terms


def _has_any(text: str, keywords: list[str]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)


def _unique(values: list[str]) -> list[str]:
    result = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result
