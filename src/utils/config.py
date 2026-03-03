"""Layered configuration module with startup validation.

Loads config in order of precedence (highest wins):
  1. Environment variables (from .env or system)
  2. Environment-specific YAML file (configs/{APP_ENV}.yaml)
  3. Hardcoded defaults

Fails fast at startup if required values are missing or invalid.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class LoggingSettings(BaseModel):
    """Logging configuration."""

    level: str = "INFO"
    format: str = "json"
    show_locals: bool = False


class ServerSettings(BaseModel):
    """Application server configuration."""

    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    reload: bool = False


class EmbeddingSettings(BaseModel):
    """Embedding model configuration."""

    model_name: str = "BAAI/bge-large-en-v1.5"
    dimension: int = 1024
    batch_size: int = 32
    device: str = "cpu"


class VectorStoreSettings(BaseModel):
    """Vector store configuration."""

    collection_name: str = "knowledge_hub"
    persist_directory: str = "data/vectorstore"
    distance_metric: str = "cosine"
    url: str = "http://localhost:6333"


class LLMSettings(BaseModel):
    """LLM client configuration."""

    api_key: str = ""
    model_id: str = "claude-sonnet-4-20250514"
    max_tokens: int = 1024
    temperature: float = 0.3
    timeout_seconds: int = 60
    vllm_base_url: str = "http://localhost:8001/v1"
    vllm_model: str = "Qwen/Qwen2.5-14B-Instruct"


class ChunkingSettings(BaseModel):
    """Text chunking configuration."""

    chunk_size: int = 1000
    chunk_overlap: int = 200
    min_chunk_size: int = 50


class FileStoreSettings(BaseModel):
    """Original file storage configuration."""

    base_directory: str = "data/originals"
    max_file_size_mb: int = 50


class RAGSettings(BaseModel):
    """RAG pipeline configuration."""

    top_k: int = 5
    similarity_threshold: float = 0.3
    max_context_tokens: int = 4000


class RedisSettings(BaseModel):
    """Redis cache configuration."""

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: str = ""
    default_ttl_days: int = 7
    url: str = ""

    @property
    def connection_url(self) -> str:
        if self.url:
            return self.url
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


class CatalogSettings(BaseModel):
    """Source catalog database configuration."""

    database_path: str = "data/catalog.db"


class GoogleDriveSettings(BaseModel):
    """Google Drive integration configuration."""

    credentials_file: str = "configs/gdrive_credentials.json"
    token_file: str = "data/gdrive_token.json"
    folder_id: str = ""
    scopes: list[str] = Field(
        default_factory=lambda: ["https://www.googleapis.com/auth/drive.readonly"]
    )


class Neo4jSettings(BaseModel):
    """Neo4j knowledge graph configuration."""

    url: str = "bolt://localhost:7687"
    user: str = "neo4j"
    password: str = ""
    database: str = "knowledgehub"


class BooksSettings(BaseModel):
    """Book library configuration."""

    storage_dir: str = "/opt/document-store/books/"
    covers_dir: str = "/opt/document-store/covers/"
    chunk_size: int = 1000
    chunk_overlap: int = 200
    embedding_batch_size: int = 32
    qdrant_collection: str = "books"
    database_path: str = "data/catalog.db"
    supported_formats: list[str] = Field(
        default_factory=lambda: [".pdf", ".epub", ".docx", ".txt", ".md"]
    )


class Settings(BaseSettings):
    """Root application settings.

    Merges environment variables, YAML config, and defaults.
    Validates at startup — the app will not start with invalid config.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # ---- Top-level ----
    app_env: str = "dev"
    app_debug: bool = True
    secret_key: str = "CHANGE-ME-IN-PRODUCTION"
    use_mocks: bool = True
    model_backend: str = "mock"

    # ---- Nested settings ----
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    server: ServerSettings = Field(default_factory=ServerSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    vector_store: VectorStoreSettings = Field(default_factory=VectorStoreSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    chunking: ChunkingSettings = Field(default_factory=ChunkingSettings)
    file_store: FileStoreSettings = Field(default_factory=FileStoreSettings)
    rag: RAGSettings = Field(default_factory=RAGSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    catalog: CatalogSettings = Field(default_factory=CatalogSettings)
    google_drive: GoogleDriveSettings = Field(default_factory=GoogleDriveSettings)
    books: BooksSettings = Field(default_factory=BooksSettings)
    neo4j: Neo4jSettings = Field(default_factory=Neo4jSettings)

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, v: str) -> str:
        allowed = {"dev", "staging", "production", "test", "local"}
        if v not in allowed:
            msg = f"app_env must be one of {allowed}, got '{v}'"
            raise ValueError(msg)
        return v

    @field_validator("model_backend")
    @classmethod
    def validate_model_backend(cls, v: str) -> str:
        allowed = {"mock", "local", "cloud"}
        if v not in allowed:
            msg = f"model_backend must be one of {allowed}, got '{v}'"
            raise ValueError(msg)
        return v

    @model_validator(mode="after")
    def validate_production_settings(self) -> Settings:
        """Fail fast if production config is incomplete."""
        if self.app_env == "production":
            if self.secret_key == "CHANGE-ME-IN-PRODUCTION":
                msg = "SECRET_KEY must be set in production"
                raise ValueError(msg)
            if self.app_debug:
                msg = "APP_DEBUG must be false in production"
                raise ValueError(msg)
        return self


def _load_yaml_config(env: str) -> dict[str, Any]:
    """Load environment-specific YAML config if it exists."""
    config_path = PROJECT_ROOT / "configs" / f"{env}.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    return {}


def load_settings() -> Settings:
    """Create and validate application settings.

    Merges: defaults < YAML config < environment variables.
    """
    import os

    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")

    env = os.getenv("APP_ENV", "dev")
    yaml_config = _load_yaml_config(env)

    return Settings(**yaml_config)


# Singleton — import this from anywhere
settings = load_settings()
