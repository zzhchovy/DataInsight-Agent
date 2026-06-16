from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.paths import (  # noqa: E402
    charts_dir,
    data_uploads_dir,
    document_uploads_dir,
    ensure_storage_dirs,
    sqlite_dir,
    storage_root,
    vector_db_dir,
)
from app.retrieval.local_agentic import infer_corpus  # noqa: E402
from app.services.document_loader import load_document  # noqa: E402
from app.services.metadata_store import init_metadata_db, record_dataset, record_document  # noqa: E402
from app.services.text_splitter import split_documents  # noqa: E402
from app.services.vector_store import VectorStore  # noqa: E402


DEMO_DOC_PATH = PROJECT_ROOT / "examples" / "energy_demo" / "docs" / "boiler_efficiency.md"
DEMO_DATA_PATH = PROJECT_ROOT / "examples" / "energy_demo" / "data" / "plant_daily.csv"
DEMO_DOCUMENT_ID = "energy_demo_boiler_efficiency.md"
DEMO_DATASET_ID = "energy_demo_plant_daily.csv"


def main() -> None:
    args = parse_args()
    root = storage_root().resolve()

    print(f"Storage root: {root}")
    if not args.yes:
        print("This command removes local generated demo data under the storage root.")
        print("Re-run with --yes to continue.")
        return

    reset_generated_storage(root)
    ensure_storage_dirs()
    init_metadata_db()
    ingest_demo()

    print("")
    print("Energy Demo reset complete.")
    print("- Document: boiler_efficiency.md")
    print("- Dataset : plant_daily.csv")
    print("- Try    : http://127.0.0.1:8501")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset generated local data and re-import the Energy Demo.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually delete generated local storage files before re-importing demo data.",
    )
    return parser.parse_args()


def reset_generated_storage(root: Path) -> None:
    targets = [
        document_uploads_dir(),
        data_uploads_dir(),
        vector_db_dir(),
        charts_dir(),
        sqlite_dir(),
        root / "demo_artifacts",
    ]
    for target in targets:
        safe_remove(target=target.resolve(), root=root)


def safe_remove(*, target: Path, root: Path) -> None:
    if not is_relative_to(target, root):
        raise RuntimeError(f"Refusing to remove path outside storage root: {target}")
    if target == root:
        raise RuntimeError(f"Refusing to remove storage root itself: {target}")
    if not target.exists():
        return
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    print(f"Removed: {target}")


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def ingest_demo() -> None:
    if not DEMO_DOC_PATH.exists():
        raise FileNotFoundError(f"Missing demo document: {DEMO_DOC_PATH}")
    if not DEMO_DATA_PATH.exists():
        raise FileNotFoundError(f"Missing demo dataset: {DEMO_DATA_PATH}")

    document_target = document_uploads_dir() / DEMO_DOCUMENT_ID
    shutil.copyfile(DEMO_DOC_PATH, document_target)

    documents = load_document(document_target, source_name=DEMO_DOC_PATH.name)
    chunks = split_documents(documents)
    chunks_added = VectorStore().add_chunks(chunks)
    record_document(
        file_id=DEMO_DOCUMENT_ID,
        filename=DEMO_DOC_PATH.name,
        file_type=DEMO_DOC_PATH.suffix.lower().lstrip("."),
        corpus=infer_corpus(DEMO_DOC_PATH.name),
        chunk_count=chunks_added,
        saved_path=str(document_target),
    )

    dataset_target = data_uploads_dir() / DEMO_DATASET_ID
    shutil.copyfile(DEMO_DATA_PATH, dataset_target)
    dataframe = pd.read_csv(dataset_target)
    record_dataset(
        dataset_id=DEMO_DATASET_ID,
        filename=DEMO_DATA_PATH.name,
        file_type=DEMO_DATA_PATH.suffix.lower().lstrip("."),
        row_count=int(len(dataframe)),
        columns=[str(column) for column in dataframe.columns.tolist()],
        saved_path=str(dataset_target),
    )


if __name__ == "__main__":
    main()
