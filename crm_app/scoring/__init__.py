"""Kural tabanlı araştırma hedefi skorlama (FAZ 2+).

Alt modüller doğrudan import edilebilir:
    from crm_app.scoring.surlas_scoring_v1 import compute_fit_score

Paket kökünden isim çözümü (tembel yükleme):
"""

from __future__ import annotations

__all__ = [
    "apply_missing_data_penalties",
    "compute_fit_score",
    "load_scoring_config",
    "score_evidence_completeness",
    "score_operational_fields",
    "score_product_signals",
    "score_sector_match",
]


def __getattr__(name: str):
    if name in __all__:
        from crm_app.scoring import surlas_scoring_v1 as mod

        return getattr(mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
