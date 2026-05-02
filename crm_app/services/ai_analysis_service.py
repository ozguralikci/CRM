"""AI firma analizi (FAZ 3B/3C-A/3C-B). Mock varsayılan; panelde OpenAI isteğe bağlı."""

from __future__ import annotations

from typing import Any

from crm_app.config.ai_settings import effective_openai_model, load_ai_settings
from crm_app.models.research_target import ResearchTarget
from crm_app.services.ai_prompts import build_research_target_ai_messages
from crm_app.services.openai_client import (
    OpenAIAnalysisClientError,
    OpenAIInvalidResponseJsonError,
    OpenAIMissingApiKeyError,
    complete_ai_analysis_json,
)


class OpenAINotActiveError(RuntimeError):
    """Dialog akışında OpenAI henüz kullanılmıyor (FAZ 3C-A uyumu)."""

    def __init__(self, message: str = "OpenAI entegrasyonu henüz aktif değil.") -> None:
        super().__init__(message)


class AiAnalysisSchemaError(ValueError):
    """Panel birleşik AI JSON şeması doğrulanamadı."""


_UNIFIED_STR_KEYS: tuple[str, ...] = (
    "summary",
    "sector",
    "sales_strategy",
    "first_message",
    "company_type",
    "production_structure",
    "product_fit_signals",
    "notes_suggestion",
    "technical_usage",
    "sealing_need",
    "sealing_where",
    "sales_difficulty",
)
_UNIFIED_LIST_KEYS: tuple[str, ...] = ("products", "departments", "risks", "surlas_fit_products")

_DECISION_ALLOWED = frozenset({"TAKİP ET", "BEKLET", "ELE", "belirsiz"})


def _ensure_mock_provider_for_dialog_only() -> None:
    if load_ai_settings().provider == "openai":
        raise OpenAINotActiveError()


def _as_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _as_str_list(val: Any) -> list[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    if isinstance(val, str) and val.strip():
        return [val.strip()]
    return []


def _as_fit_score_percent(val: Any) -> int:
    if val is None or val == "":
        return 0
    if isinstance(val, bool):
        raise AiAnalysisSchemaError("fit_score_percent geçersiz.")
    if isinstance(val, (int, float)):
        n = int(round(float(val)))
    else:
        try:
            n = int(str(val).strip())
        except ValueError as e:
            raise AiAnalysisSchemaError("fit_score_percent sayı değil.") from e
    return max(0, min(100, n))


def _normalize_decision(val: Any) -> str:
    s = _as_str(val)
    if not s:
        return "belirsiz"
    up = s.upper()
    if up in ("TAKİP ET", "TAKIP ET"):
        return "TAKİP ET"
    if up == "BEKLET":
        return "BEKLET"
    if up == "ELE":
        return "ELE"
    if s.lower() == "belirsiz":
        return "belirsiz"
    if s in _DECISION_ALLOWED:
        return s
    raise AiAnalysisSchemaError(
        f"decision geçersiz: {s!r} (TAKİP ET, BEKLET, ELE veya belirsiz olmalı)"
    )


def validate_and_normalize_panel_ai_dict(raw: dict[str, Any]) -> dict[str, Any]:
    """Panel/OpenAI birleşik şema — DB öncesi doğrulama."""
    if not isinstance(raw, dict):
        raise AiAnalysisSchemaError("Kök nesne bekleniyordu.")

    out: dict[str, Any] = {}
    for key in _UNIFIED_STR_KEYS:
        if key not in raw:
            raise AiAnalysisSchemaError(f"Eksik alan: {key}")
        if not isinstance(raw[key], (str, int, float, type(None))):
            raise AiAnalysisSchemaError(f"Alan tipi geçersiz: {key}")
        out[key] = _as_str(raw[key])

    for key in _UNIFIED_LIST_KEYS:
        if key not in raw:
            raise AiAnalysisSchemaError(f"Eksik alan: {key}")
        if not isinstance(raw[key], list):
            raise AiAnalysisSchemaError(f"Dizi bekleniyordu: {key}")
        out[key] = _as_str_list(raw[key])

    if "fit_score_percent" not in raw:
        raise AiAnalysisSchemaError("Eksik alan: fit_score_percent")
    out["fit_score_percent"] = _as_fit_score_percent(raw["fit_score_percent"])

    if "decision" not in raw:
        raise AiAnalysisSchemaError("Eksik alan: decision")
    out["decision"] = _normalize_decision(raw["decision"])

    out["schema_version"] = "ai_analysis_v2"
    return out


def format_panel_ai_user_message(exc: BaseException) -> str:
    """Panel hata kutusu için Türkçe özet."""
    if isinstance(exc, OpenAIMissingApiKeyError):
        return str(exc)
    if isinstance(exc, AiAnalysisSchemaError):
        return f"Geçersiz JSON / şema: {exc}"
    if isinstance(exc, OpenAIInvalidResponseJsonError):
        return f"Geçersiz JSON: {exc}"
    if isinstance(exc, OpenAIAnalysisClientError):
        low = str(exc).lower()
        if "timeout" in low or "timed out" in low:
            return "İstek zaman aşımına uğradı. Daha sonra tekrar deneyin."
        if "connection" in low or "connect" in low:
            return "OpenAI sunucusuna bağlanılamadı. Ağ bağlantınızı kontrol edin."
        if "429" in low or "rate" in low:
            return "OpenAI kota sınırı nedeniyle istek reddedildi. Daha sonra tekrar deneyin."
        return f"OpenAI API hatası: {exc}"
    return f"İşlem başarısız: {exc}"


def _mock_panel_unified_payload() -> dict[str, Any]:
    return {
        "summary": "Üretim hattında sıvı/gaz bağlantılarında teknik conta ihtimali; kanıt sınırlı.",
        "sector": "Otomotiv Yan Sanayi",
        "products": ["Statik conta", "FKM O-ring"],
        "departments": ["Satın alma", "Üretim bakım"],
        "sales_strategy": "Teknik veri ve numune onayı ile satın alma ile temas.",
        "risks": ["Fiyat rekabeti", "OEM onay sureci"],
        "first_message": (
            "Üretim hatlarınızdaki sızdırmazlık ihtiyacı için teknik kısa değerlendirme paylaşabilir miyiz?"
        ),
        "company_type": "Üretici",
        "production_structure": "Seri üretim",
        "product_fit_signals": "Conta, O-ring, sızdırmazlık elemanları kullanımı",
        "notes_suggestion": "Hat bazlı conta tipi ve standart (DIN/ISO) netleştirin.",
        "technical_usage": (
            "Montaj istasyonları ve hidrolik/pnömatik hat bağlantıları (kayıtta detay yok; belirsiz)."
        ),
        "sealing_need": "belirsiz",
        "sealing_where": "belirsiz",
        "surlas_fit_products": ["Kauçuk conta", "O-ring"],
        "sales_difficulty": "Orta — teknik onay ve çoklu tedarikçi rekabeti.",
        "fit_score_percent": 55,
        "decision": "BEKLET",
    }


def run_ai_suggest_for_dialog(context: dict[str, Any]) -> dict[str, Any]:
    """
    Yeni Hedef dialogu icin AI onerisi (mock). Harici cagri yok.
    context: firma adi, web, linkedin, ulke, sehir vb. (ileride prompt icin).
    """
    _ensure_mock_provider_for_dialog_only()
    _ = context
    return {
        "schema_version": "ai_analysis_v1",
        "summary": "Bu firma üretim odaklıdır.",
        "sector": "Otomotiv Yan Sanayi",
        "company_type": "Üretici",
        "production_structure": "Seri üretim",
        "product_fit_signals": "Conta, O-ring, sızdırmazlık elemanları kullanımı",
        "suitability_comment": "Orta seviye uygunluk.",
        "target_roles": ["Satın alma", "Üretim Müdürü"],
        "sales_approach": "Teknik satış yaklaşımı önerilir.",
        "risks": ["Fiyat rekabeti"],
        "notes_suggestion": "Sızdırmazlık çözümleri sunulabilir.",
        "disclaimer": "AI önerisidir.",
    }


def run_ai_analysis_for_target(target: ResearchTarget) -> dict[str, Any]:
    """
    Seçili hedef için AI analiz çıktısı.
    AI_PROVIDER=mock: yerel mock (birleşik şema).
    AI_PROVIDER=openai: OpenAI (retry yok); şema hatalıysa exception.
    """
    settings = load_ai_settings()
    if settings.provider == "mock":
        return validate_and_normalize_panel_ai_dict(_mock_panel_unified_payload())

    if settings.provider != "openai":
        return validate_and_normalize_panel_ai_dict(_mock_panel_unified_payload())

    if not settings.openai_api_key:
        raise OpenAIMissingApiKeyError(
            "OPENAI_API_KEY ortam değişkeni tanımlı değil. .env veya sistem ortamına ekleyin."
        )

    max_chars = min(2000, max(256, settings.openai_max_prompt_chars))
    messages = build_research_target_ai_messages(target, max_chars=max_chars)
    model = effective_openai_model(settings)
    raw = complete_ai_analysis_json(
        messages,
        model=model,
        timeout=settings.openai_timeout_sec,
        max_output_tokens=settings.openai_max_output_tokens,
    )
    return validate_and_normalize_panel_ai_dict(raw)
