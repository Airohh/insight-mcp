"""Runtime configuration, loaded from environment variables / .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root when running from a checkout (src layout: src/insight_mcp/settings.py).
# The MCP client may spawn the server from any working directory, so relative
# defaults must not depend on cwd. Override with DATA_DIR for other layouts.
_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    corpus_seed_file: Path = _REPO_ROOT / "scripts" / "seed_urls_wavestone.txt"
    data_dir: Path = _REPO_ROOT / "data"
    search_mode: Literal["bm25", "hybrid"] = "bm25"
    embed_model: str = "BAAI/bge-small-en-v1.5"  # hybrid mode only (fastembed)
    mcp_auth_token: str = ""  # HTTP transport only
    mcp_port: int = 8020  # HTTP transport only
    rate_limit_per_minute: int = 60  # HTTP transport; 0 disables

    @property
    def db_path(self) -> Path:
        return self.data_dir / "corpus.db"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "raw"


@lru_cache
def get_settings() -> Settings:
    return Settings()
