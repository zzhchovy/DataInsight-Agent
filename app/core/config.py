from functools import lru_cache
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the local MVP."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "DataInsight-Agent"
    storage_dir: Path = Field(
        default=Path("storage"),
        validation_alias="DATAINSIGHT_STORAGE_DIR",
    )
    vector_collection: str = Field(
        default="data_insight_documents",
        validation_alias="DATAINSIGHT_VECTOR_COLLECTION",
    )
    chunk_size: int = Field(default=900, validation_alias="DATAINSIGHT_CHUNK_SIZE")
    chunk_overlap: int = Field(default=120, validation_alias="DATAINSIGHT_CHUNK_OVERLAP")
    retrieval_backend: str = Field(
        default="local_agentic_rag",
        validation_alias="RETRIEVAL_BACKEND",
    )
    llm_provider: str = Field(default="none", validation_alias="DATAINSIGHT_LLM_PROVIDER")
    llm_model: str = Field(default="gpt-4o-mini", validation_alias="DATAINSIGHT_LLM_MODEL")
    llm_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias="DATAINSIGHT_LLM_BASE_URL",
    )
    llm_api_key: str | None = Field(default=None, validation_alias="DATAINSIGHT_LLM_API_KEY")
    llm_timeout_seconds: float = Field(
        default=30.0,
        validation_alias="DATAINSIGHT_LLM_TIMEOUT_SECONDS",
    )
    google_cloud_project: str | None = Field(
        default=None,
        validation_alias="GOOGLE_CLOUD_PROJECT",
    )
    google_cloud_location: str = Field(
        default="us-central1",
        validation_alias="GOOGLE_CLOUD_LOCATION",
    )
    google_rag_corpus_ids: str | None = Field(
        default=None,
        validation_alias="GOOGLE_RAG_CORPUS_IDS",
    )
    google_application_credentials: str | None = Field(
        default=None,
        validation_alias="GOOGLE_APPLICATION_CREDENTIALS",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
