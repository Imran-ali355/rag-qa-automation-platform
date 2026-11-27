"""Validated application configuration, loaded without starting external services."""

from dataclasses import dataclass
import math
import os
from pathlib import Path
import re
from urllib.parse import urlsplit


def _integer(env: dict, key: str, default: int, minimum: int, maximum: int) -> int:
    value = env.get(key, str(default))
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be an integer.") from exc
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{key} must be between {minimum} and {maximum}.")
    return parsed


def _number(env: dict, key: str, default: float, minimum: float, maximum: float) -> float:
    try:
        parsed = float(env.get(key, str(default)))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a number.") from exc
    if not math.isfinite(parsed) or not minimum <= parsed <= maximum:
        raise ValueError(f"{key} must be finite and between {minimum} and {maximum}.")
    return parsed


@dataclass(frozen=True)
class Config:
    docs_dir: Path
    db_dir: Path
    collection_name: str
    ollama_base_url: str
    chat_model: str
    embed_model: str
    max_distance: float
    top_k: int
    chunk_size: int
    chunk_overlap: int
    max_cases: int
    max_question_chars: int
    max_request_bytes: int
    ollama_connect_timeout: float
    ollama_embed_timeout: float
    ollama_read_timeout: float
    port: int

    @classmethod
    def from_env(cls, env=None) -> "Config":
        env = os.environ if env is None else env
        url = env.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
        parsed_url = urlsplit(url)
        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.netloc
            or parsed_url.username is not None
            or parsed_url.password is not None
            or parsed_url.query
            or parsed_url.fragment
        ):
            raise ValueError("OLLAMA_BASE_URL must be an absolute HTTP(S) URL.")
        collection = env.get("COLLECTION_NAME", "local_rag_docs")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{1,61}[A-Za-z0-9]", collection):
            raise ValueError("COLLECTION_NAME is invalid.")
        chat_model = env.get("CHAT_MODEL", "llama3.2").strip()
        embed_model = env.get("EMBED_MODEL", "nomic-embed-text").strip()
        if not chat_model or not embed_model:
            raise ValueError("CHAT_MODEL and EMBED_MODEL must not be empty.")
        chunk_size = _integer(env, "CHUNK_SIZE", 500, 1, 100000)
        chunk_overlap = _integer(env, "CHUNK_OVERLAP", 80, 0, 99999)
        if chunk_overlap >= chunk_size:
            raise ValueError("CHUNK_OVERLAP must be smaller than CHUNK_SIZE.")
        return cls(
            docs_dir=Path(env.get("DOCS_DIR", "docs")),
            db_dir=Path(env.get("DB_DIR", "chroma_txt_db")),
            collection_name=collection,
            ollama_base_url=url,
            chat_model=chat_model,
            embed_model=embed_model,
            max_distance=_number(env, "MAX_DISTANCE", 1.0, 0.0, 2.0),
            top_k=_integer(env, "TOP_K", 5, 1, 100),
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            max_cases=_integer(env, "MAX_CASES", 8, 1, 8),
            max_question_chars=_integer(env, "MAX_QUESTION_CHARS", 4000, 1, 100000),
            max_request_bytes=_integer(env, "MAX_REQUEST_BYTES", 65536, 1, 10485760),
            ollama_connect_timeout=_number(env, "OLLAMA_CONNECT_TIMEOUT", 5.0, 0.1, 60.0),
            ollama_embed_timeout=_number(env, "OLLAMA_EMBED_TIMEOUT", 60.0, 0.1, 600.0),
            ollama_read_timeout=_number(env, "OLLAMA_READ_TIMEOUT", 180.0, 0.1, 600.0),
            port=_integer(env, "PORT", 5000, 1, 65535),
        )
