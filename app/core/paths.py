from pathlib import Path

from app.core.config import get_settings


def storage_root() -> Path:
    return get_settings().storage_dir


def uploads_dir() -> Path:
    return storage_root() / "uploads"


def document_uploads_dir() -> Path:
    return uploads_dir() / "documents"


def data_uploads_dir() -> Path:
    return uploads_dir() / "data"


def vector_db_dir() -> Path:
    return storage_root() / "vector_db"


def charts_dir() -> Path:
    return storage_root() / "charts"


def sqlite_dir() -> Path:
    return storage_root() / "sqlite"


def metadata_db_path() -> Path:
    return sqlite_dir() / "metadata.sqlite3"


def ensure_storage_dirs() -> None:
    for path in [
        storage_root(),
        uploads_dir(),
        document_uploads_dir(),
        data_uploads_dir(),
        vector_db_dir(),
        charts_dir(),
        sqlite_dir(),
    ]:
        path.mkdir(parents=True, exist_ok=True)
