"""AI sağlayıcı ayarları — yalnızca ortam değişkenleri (FAZ 3C-A)."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _parse_positive_int(value: str | None, *, default: int) -> int:
    if value is None or not str(value).strip():
        return default
    try:
        n = int(str(value).strip())
        return n if n > 0 else default
    except ValueError:
        return default


def _parse_positive_float(value: str | None, *, default: float) -> float:
    if value is None or not str(value).strip():
        return default
    try:
        x = float(str(value).strip())
        return x if x > 0 else default
    except ValueError:
        return default


def _normalize_provider(raw: str | None) -> str:
    p = (raw or "mock").strip().lower() or "mock"
    if p == "openai":
        return "openai"
    return "mock"


@dataclass(frozen=True)
class AiSettings:
    """Ortamdan okunan AI ayarları (crm.sqlite ile ilgisi yok)."""

    provider: str
    openai_api_key: str | None
    openai_model: str | None
    openai_timeout_sec: float
    openai_max_output_tokens: int
    openai_max_prompt_chars: int


def load_ai_settings() -> AiSettings:
    provider = _normalize_provider(os.getenv("AI_PROVIDER"))

    key_raw = os.getenv("OPENAI_API_KEY")
    openai_api_key = None
    if key_raw is not None:
        s = key_raw.strip()
        openai_api_key = s if s else None

    model_raw = os.getenv("OPENAI_MODEL")
    openai_model = None
    if model_raw is not None:
        m = model_raw.strip()
        openai_model = m if m else None

    return AiSettings(
        provider=provider,
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        openai_timeout_sec=_parse_positive_float(os.getenv("OPENAI_TIMEOUT_SEC"), default=45.0),
        openai_max_output_tokens=_parse_positive_int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS"), default=1200),
        openai_max_prompt_chars=_parse_positive_int(os.getenv("OPENAI_MAX_PROMPT_CHARS"), default=4000),
    )
