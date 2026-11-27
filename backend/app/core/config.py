"""Configurações centralizadas da API ErgoAI (pydantic-settings)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Configurações de ambiente, segurança (RNF03) e caminhos do RAG."""

    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    allowed_origins: str = "http://localhost:5173,http://localhost:8000"
    enforce_https: bool = False

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    chroma_persist_dir: str = str(BACKEND_DIR / "data" / "chroma")
    corpus_chunks_path: str = str(REPO_ROOT / "knowledge_base" / "corpus" / "chunks.jsonl")
    kb_manifest_path: str = str(REPO_ROOT / "knowledge_base" / "processed" / "manifest.json")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"

    @property
    def https_required(self) -> bool:
        return self.is_production or self.enforce_https


@lru_cache
def get_settings() -> Settings:
    """Retorna instância cacheada de Settings."""
    return Settings()
