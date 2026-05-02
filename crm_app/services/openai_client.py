"""OpenAI Chat Completions — panel AI analizi (FAZ 3C-B). Ağ çağrısı yalnız burada."""

from __future__ import annotations

import json
import os
from typing import Any

from openai import (
    APIConnectionError,
    APITimeoutError,
    BadRequestError,
    OpenAI,
    RateLimitError,
)


class OpenAIAnalysisClientError(RuntimeError):
    """OpenAI istemci katmanı hataları."""


class OpenAIMissingApiKeyError(OpenAIAnalysisClientError):
    """OPENAI_API_KEY tanımlı değil."""


class OpenAIInvalidResponseJsonError(OpenAIAnalysisClientError):
    """Yanıt JSON olarak işlenemedi veya boş."""


# Strict Structured Outputs için (OpenAI: additionalProperties false, tüm alanlar required)
UNIFIED_AI_ANALYSIS_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "sector": {"type": "string"},
        "products": {"type": "array", "items": {"type": "string"}},
        "departments": {"type": "array", "items": {"type": "string"}},
        "sales_strategy": {"type": "string"},
        "risks": {"type": "array", "items": {"type": "string"}},
        "first_message": {"type": "string"},
        "company_type": {"type": "string"},
        "production_structure": {"type": "string"},
        "product_fit_signals": {"type": "string"},
        "notes_suggestion": {"type": "string"},
        "technical_usage": {"type": "string"},
        "sealing_need": {"type": "string"},
        "sealing_where": {"type": "string"},
        "surlas_fit_products": {"type": "array", "items": {"type": "string"}},
        "sales_difficulty": {"type": "string"},
        "fit_score_percent": {"type": "integer", "minimum": 0, "maximum": 100},
        "decision": {
            "type": "string",
            "enum": ["TAKİP ET", "BEKLET", "ELE", "belirsiz"],
        },
    },
    "required": [
        "summary",
        "sector",
        "products",
        "departments",
        "sales_strategy",
        "risks",
        "first_message",
        "company_type",
        "production_structure",
        "product_fit_signals",
        "notes_suggestion",
        "technical_usage",
        "sealing_need",
        "sealing_where",
        "surlas_fit_products",
        "sales_difficulty",
        "fit_score_percent",
        "decision",
    ],
}


def _parse_message_content(completion: Any) -> str:
    choice0 = completion.choices[0]
    msg = choice0.message
    content = getattr(msg, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
        return "".join(parts).strip()
    return ""


def complete_ai_analysis_json(
    messages: list[dict[str, Any]],
    model: str,
    timeout: float,
    max_output_tokens: int,
) -> dict[str, Any]:
    """
    Tek tamamlama isteği (retry yok).
    Önce json_schema (strict); desteklenmiyorsa tek ek istek ile json_object (API format hatası için).
    """
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise OpenAIMissingApiKeyError(
            "OPENAI_API_KEY ortam değişkeni tanımlı değil. .env veya sistem ortamına ekleyin."
        )

    client = OpenAI(api_key=api_key, timeout=timeout)
    base_kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_output_tokens,
    }

    schema_wrapped = {
        "type": "json_schema",
        "json_schema": {
            "name": "research_target_ai_analysis",
            "strict": True,
            "schema": UNIFIED_AI_ANALYSIS_JSON_SCHEMA,
        },
    }

    completion = None
    try:
        completion = client.chat.completions.create(
            **base_kwargs,
            response_format=schema_wrapped,  # type: ignore[arg-type]
        )
    except BadRequestError as e:
        err_body = (getattr(e, "message", None) or str(e)).lower()
        if getattr(e, "status_code", None) == 400 and (
            "json_schema" in err_body or "response_format" in err_body
        ):
            try:
                completion = client.chat.completions.create(
                    **base_kwargs,
                    response_format={"type": "json_object"},
                )
            except Exception as e2:
                raise OpenAIAnalysisClientError(f"OpenAI API hatası (json_object): {e2}") from e2
        else:
            raise OpenAIAnalysisClientError(f"OpenAI API hatası (400): {e}") from e
    except (RateLimitError, APIConnectionError, APITimeoutError) as e:
        raise OpenAIAnalysisClientError(str(e)) from e
    except OpenAIAnalysisClientError:
        raise
    except Exception as e:
        raise OpenAIAnalysisClientError(f"OpenAI isteği başarısız: {e}") from e

    if completion is None:
        raise OpenAIInvalidResponseJsonError("OpenAI yanıtı alınamadı.")

    text = _parse_message_content(completion)
    if not text:
        raise OpenAIInvalidResponseJsonError("OpenAI boş içerik döndürdü.")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise OpenAIInvalidResponseJsonError(f"Geçersiz JSON: {e}") from e

    if not isinstance(parsed, dict):
        raise OpenAIInvalidResponseJsonError("JSON kökü nesne değil.")

    return parsed
