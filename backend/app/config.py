"""
IntelliNotes backend configuration.

Loads settings from environment variables / .env file with validation.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-flash-lite-latest"

    # Embeddings
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Chunking
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64

    # Retrieval
    TOP_K: int = 5
    SIMILARITY_THRESHOLD: float = 0.25

    # Upload
    MAX_UPLOAD_MB: int = 20

    # Data directory
    DATA_DIR: str = "./data"

    model_config = SettingsConfigDict(
        env_file=[str(Path(__file__).parent.parent / ".env"), ".env"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("CHUNK_SIZE")
    @classmethod
    def chunk_size_positive(cls, v: int) -> int:
        if v < 64:
            raise ValueError("CHUNK_SIZE must be at least 64")
        return v

    @field_validator("CHUNK_OVERLAP")
    @classmethod
    def chunk_overlap_valid(cls, v: int, info) -> int:
        if v < 0:
            raise ValueError("CHUNK_OVERLAP must be non-negative")
        return v

    @field_validator("TOP_K")
    @classmethod
    def top_k_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("TOP_K must be at least 1")
        return v

    @field_validator("SIMILARITY_THRESHOLD")
    @classmethod
    def threshold_valid(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("SIMILARITY_THRESHOLD must be between 0.0 and 1.0")
        return v

    @field_validator("MAX_UPLOAD_MB")
    @classmethod
    def max_upload_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("MAX_UPLOAD_MB must be at least 1")
        return v

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024

    @property
    def data_path(self) -> Path:
        p = Path(self.DATA_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def db_path(self) -> Path:
        return self.data_path / "intellinotes.db"

    @property
    def index_path(self) -> Path:
        return self.data_path / "faiss.index"

    @property
    def chunk_map_path(self) -> Path:
        return self.data_path / "chunk_map.json"

    @property
    def uploads_path(self) -> Path:
        p = self.data_path / "uploads"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def validate_chunk_settings(self) -> None:
        """Validate that overlap is less than chunk size."""
        if self.CHUNK_OVERLAP >= self.CHUNK_SIZE:
            raise ValueError(
                f"CHUNK_OVERLAP ({self.CHUNK_OVERLAP}) must be less than "
                f"CHUNK_SIZE ({self.CHUNK_SIZE})"
            )


def get_settings() -> Settings:
    """Create and validate settings instance."""
    settings = Settings()
    settings.validate_chunk_settings()
    return settings
