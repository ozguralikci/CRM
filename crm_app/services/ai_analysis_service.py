"""AI firma analizi (FAZ 3B/3C-A). Mock varsayılan; OpenAI sonraki adımda."""

from __future__ import annotations

from typing import Any

from crm_app.config.ai_settings import load_ai_settings
from crm_app.models.research_target import ResearchTarget


class OpenAINotActiveError(RuntimeError):
    """AI_PROVIDER=openai iken gerçek entegrasyon henüz yoksa."""

    def __init__(self, message: str = "OpenAI entegrasyonu henüz aktif değil.") -> None:
        super().__init__(message)


def _ensure_mock_provider_or_raise() -> None:
    if load_ai_settings().provider == "openai":
        raise OpenAINotActiveError()


def run_ai_suggest_for_dialog(context: dict[str, Any]) -> dict[str, Any]:
    """
    Yeni Hedef dialogu icin AI onerisi (mock). Harici cagri yok.
    context: firma adi, web, linkedin, ulke, sehir vb. (ileride prompt icin).
    """
    _ensure_mock_provider_or_raise()
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
    Seçili hedef için AI analiz çıktısı üretir (mock).
    Gerçek OpenAI entegrasyonu sonraki fazda buraya bağlanır.
    """
    _ensure_mock_provider_or_raise()
    _ = target  # İleride prompt bağlamı için kullanılacak
    return {
        "schema_version": "ai_analysis_v1",
        "summary": "Bu firma üretim odaklıdır.",
        "suitability": "Orta seviye uygunluk.",
        "products": ["Conta", "O-ring"],
        "departments": ["Satın alma", "Üretim"],
        "sales_strategy": "Teknik satış yaklaşımı önerilir.",
        "risks": ["Fiyat rekabeti"],
        "first_message": "Merhaba, üretim süreçlerinize çözüm sunmak isteriz.",
        "confidence_notes": "Veri sınırlı.",
        "disclaimer": "AI önerisidir.",
    }
