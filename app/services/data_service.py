from pathlib import Path
import shutil
import uuid

import pandas as pd
from fastapi import UploadFile

from app.core.paths import data_uploads_dir


SUPPORTED_DATA_EXTENSIONS = {".csv", ".xlsx", ".xls"}


def save_data_upload(file: UploadFile) -> tuple[str, Path, pd.DataFrame]:
    original_name = file.filename or "dataset.csv"
    suffix = Path(original_name).suffix.lower()
    if suffix not in SUPPORTED_DATA_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_DATA_EXTENSIONS))
        raise ValueError(f"Unsupported data type: {suffix}. Supported: {supported}")

    dataset_id = f"{uuid.uuid4().hex}{suffix}"
    saved_path = data_uploads_dir() / dataset_id
    with saved_path.open("wb") as output:
        shutil.copyfileobj(file.file, output)

    dataframe = load_dataset(dataset_id)
    return dataset_id, saved_path, dataframe


def load_dataset(dataset_id: str | None = None) -> pd.DataFrame:
    path = resolve_dataset_path(dataset_id)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    return pd.read_excel(path)


def resolve_dataset_path(dataset_id: str | None = None) -> Path:
    if dataset_id:
        path = data_uploads_dir() / dataset_id
        if not path.exists():
            raise FileNotFoundError(f"Dataset not found: {dataset_id}")
        return path

    candidates = [
        path
        for path in data_uploads_dir().iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_DATA_EXTENSIONS
    ]
    if not candidates:
        raise FileNotFoundError("No dataset uploaded yet.")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def list_datasets() -> list[dict]:
    datasets = []
    for path in sorted(data_uploads_dir().iterdir(), key=lambda item: item.stat().st_mtime):
        if path.is_file() and path.suffix.lower() in SUPPORTED_DATA_EXTENSIONS:
            datasets.append(
                {
                    "dataset_id": path.name,
                    "filename": path.name,
                    "saved_path": str(path),
                    "modified_time": path.stat().st_mtime,
                }
            )
    return datasets

