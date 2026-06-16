from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import uuid
from typing import Any

from app.core.paths import metadata_db_path


def init_metadata_db(db_path: Path | None = None) -> None:
    path = db_path or metadata_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_type TEXT,
                corpus TEXT,
                chunk_count INTEGER NOT NULL DEFAULT 0,
                saved_path TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS datasets (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_type TEXT,
                row_count INTEGER NOT NULL DEFAULT 0,
                columns_json TEXT NOT NULL,
                saved_path TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS artifacts (
                id TEXT PRIMARY KEY,
                artifact_type TEXT NOT NULL,
                file_path TEXT,
                question TEXT,
                route TEXT,
                qa_id TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS qa_history (
                id TEXT PRIMARY KEY,
                question TEXT NOT NULL,
                route TEXT,
                answer TEXT,
                retrieval_backend TEXT,
                selected_corpora_json TEXT NOT NULL DEFAULT '[]',
                citations_json TEXT NOT NULL DEFAULT '[]',
                tool_calls_json TEXT NOT NULL DEFAULT '[]',
                latency_ms INTEGER,
                sufficient_context INTEGER,
                dataset_id TEXT,
                chart_path TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_documents_created_at
                ON documents(created_at);
            CREATE INDEX IF NOT EXISTS idx_datasets_created_at
                ON datasets(created_at);
            CREATE INDEX IF NOT EXISTS idx_artifacts_created_at
                ON artifacts(created_at);
            CREATE INDEX IF NOT EXISTS idx_qa_history_created_at
                ON qa_history(created_at);
            """
        )
        _ensure_column(
            conn,
            table_name="qa_history",
            column_name="tool_calls_json",
            column_definition="TEXT NOT NULL DEFAULT '[]'",
        )


def record_document(
    *,
    file_id: str,
    filename: str,
    file_type: str | None,
    corpus: str | None,
    chunk_count: int,
    saved_path: str,
) -> dict[str, Any]:
    init_metadata_db()
    row = {
        "id": file_id,
        "filename": filename,
        "file_type": file_type,
        "corpus": corpus,
        "chunk_count": int(chunk_count),
        "saved_path": saved_path,
        "created_at": _now(),
    }
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO documents (
                id, filename, file_type, corpus, chunk_count, saved_path, created_at
            ) VALUES (
                :id, :filename, :file_type, :corpus, :chunk_count, :saved_path, :created_at
            )
            ON CONFLICT(id) DO UPDATE SET
                filename = excluded.filename,
                file_type = excluded.file_type,
                corpus = excluded.corpus,
                chunk_count = excluded.chunk_count,
                saved_path = excluded.saved_path
            """,
            row,
        )
    return row


def record_dataset(
    *,
    dataset_id: str,
    filename: str,
    file_type: str | None,
    row_count: int,
    columns: list[str],
    saved_path: str,
) -> dict[str, Any]:
    init_metadata_db()
    row = {
        "id": dataset_id,
        "filename": filename,
        "file_type": file_type,
        "row_count": int(row_count),
        "columns_json": _to_json(columns),
        "saved_path": saved_path,
        "created_at": _now(),
    }
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO datasets (
                id, filename, file_type, row_count, columns_json, saved_path, created_at
            ) VALUES (
                :id, :filename, :file_type, :row_count, :columns_json, :saved_path, :created_at
            )
            ON CONFLICT(id) DO UPDATE SET
                filename = excluded.filename,
                file_type = excluded.file_type,
                row_count = excluded.row_count,
                columns_json = excluded.columns_json,
                saved_path = excluded.saved_path
            """,
            row,
        )
    return _dataset_row_to_dict(row)


def record_qa_history(
    *,
    question: str,
    route: str | None,
    answer: str | None,
    retrieval_backend: str | None,
    selected_corpora: list[str] | None,
    citations: list[dict[str, Any]] | None,
    tool_calls: list[dict[str, Any]] | None,
    latency_ms: int | None,
    sufficient_context: bool | None,
    dataset_id: str | None,
    chart_path: str | None,
) -> str:
    init_metadata_db()
    qa_id = uuid.uuid4().hex
    row = {
        "id": qa_id,
        "question": question,
        "route": route,
        "answer": answer,
        "retrieval_backend": retrieval_backend,
        "selected_corpora_json": _to_json(selected_corpora or []),
        "citations_json": _to_json(citations or []),
        "tool_calls_json": _to_json(tool_calls or []),
        "latency_ms": latency_ms,
        "sufficient_context": _bool_to_int(sufficient_context),
        "dataset_id": dataset_id,
        "chart_path": chart_path,
        "created_at": _now(),
    }
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO qa_history (
                id, question, route, answer, retrieval_backend,
                selected_corpora_json, citations_json, tool_calls_json, latency_ms,
                sufficient_context, dataset_id, chart_path, created_at
            ) VALUES (
                :id, :question, :route, :answer, :retrieval_backend,
                :selected_corpora_json, :citations_json, :tool_calls_json, :latency_ms,
                :sufficient_context, :dataset_id, :chart_path, :created_at
            )
            """,
            row,
        )
    return qa_id


def record_artifact(
    *,
    artifact_type: str,
    file_path: str | None,
    question: str | None,
    route: str | None,
    qa_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    init_metadata_db()
    row = {
        "id": uuid.uuid4().hex,
        "artifact_type": artifact_type,
        "file_path": file_path,
        "question": question,
        "route": route,
        "qa_id": qa_id,
        "metadata_json": _to_json(metadata or {}),
        "created_at": _now(),
    }
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO artifacts (
                id, artifact_type, file_path, question, route, qa_id, metadata_json, created_at
            ) VALUES (
                :id, :artifact_type, :file_path, :question, :route, :qa_id, :metadata_json, :created_at
            )
            """,
            row,
        )
    return _artifact_row_to_dict(row)


def record_agent_run(question: str, dataset_id: str | None, state: dict[str, Any]) -> str:
    qa_id = record_qa_history(
        question=question,
        route=state.get("route"),
        answer=state.get("final_answer") or state.get("answer"),
        retrieval_backend=state.get("retrieval_backend"),
        selected_corpora=state.get("selected_corpora", []),
        citations=state.get("citations", []),
        tool_calls=state.get("tool_calls", []),
        latency_ms=state.get("latency_ms"),
        sufficient_context=state.get("sufficient_context"),
        dataset_id=dataset_id,
        chart_path=state.get("chart_path"),
    )

    chart_path = state.get("chart_path")
    if chart_path:
        record_artifact(
            artifact_type="chart",
            file_path=chart_path,
            question=question,
            route=state.get("route"),
            qa_id=qa_id,
            metadata={"artifacts": state.get("artifacts", {})},
        )

    if state.get("route") == "report":
        record_artifact(
            artifact_type="report",
            file_path=None,
            question=question,
            route=state.get("route"),
            qa_id=qa_id,
            metadata={
                "answer_preview": (state.get("answer") or "")[:500],
                "citation_count": len(state.get("citations", [])),
            },
        )

    return qa_id


def list_documents(limit: int = 100) -> list[dict[str, Any]]:
    init_metadata_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, filename, file_type, corpus, chunk_count, saved_path, created_at
            FROM documents
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def list_datasets_metadata(limit: int = 100) -> list[dict[str, Any]]:
    init_metadata_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, filename, file_type, row_count, columns_json, saved_path, created_at
            FROM datasets
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_dataset_row_to_dict(dict(row)) for row in rows]


def list_artifacts(limit: int = 100) -> list[dict[str, Any]]:
    init_metadata_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, artifact_type, file_path, question, route, qa_id, metadata_json, created_at
            FROM artifacts
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_artifact_row_to_dict(dict(row)) for row in rows]


def list_qa_history(limit: int = 100) -> list[dict[str, Any]]:
    init_metadata_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT
                id, question, route, answer, retrieval_backend,
                selected_corpora_json, citations_json, tool_calls_json, latency_ms,
                sufficient_context, dataset_id, chart_path, created_at
            FROM qa_history
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_qa_row_to_dict(dict(row)) for row in rows]


def _connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or metadata_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(
    conn: sqlite3.Connection,
    *,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    columns = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _from_json(raw_value: str | None, default: Any) -> Any:
    if not raw_value:
        return default
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        return default


def _bool_to_int(value: bool | None) -> int | None:
    if value is None:
        return None
    return 1 if value else 0


def _int_to_bool(value: int | None) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _dataset_row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "filename": row["filename"],
        "file_type": row.get("file_type"),
        "row_count": row.get("row_count", 0),
        "columns": _from_json(row.get("columns_json"), []),
        "saved_path": row.get("saved_path"),
        "created_at": row["created_at"],
    }


def _artifact_row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "artifact_type": row["artifact_type"],
        "file_path": row.get("file_path"),
        "question": row.get("question"),
        "route": row.get("route"),
        "qa_id": row.get("qa_id"),
        "metadata": _from_json(row.get("metadata_json"), {}),
        "created_at": row["created_at"],
    }


def _qa_row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "question": row["question"],
        "route": row.get("route"),
        "answer": row.get("answer"),
        "retrieval_backend": row.get("retrieval_backend"),
        "selected_corpora": _from_json(row.get("selected_corpora_json"), []),
        "citations": _from_json(row.get("citations_json"), []),
        "tool_calls": _from_json(row.get("tool_calls_json"), []),
        "latency_ms": row.get("latency_ms"),
        "sufficient_context": _int_to_bool(row.get("sufficient_context")),
        "dataset_id": row.get("dataset_id"),
        "chart_path": row.get("chart_path"),
        "created_at": row["created_at"],
    }
