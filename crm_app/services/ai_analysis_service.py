"""AI firma analizi (FAZ 3B). Şimdilik mock — harici API yok."""

from __future__ import annotations

from typing import Any

from crm_app.models.research_target import ResearchTarget


def run_ai_analysis_for_target(target: ResearchTarget) -> dict[str, Any]:
    """
    Seçili hedef için AI analiz çıktısı üretir (mock).
    Gerçek OpenAI entegrasyonu sonraki fazda buraya bağlanır.
    """
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
