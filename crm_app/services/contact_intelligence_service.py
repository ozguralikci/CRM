from __future__ import annotations

from dataclasses import dataclass
import unicodedata


INTELLIGENCE_KEYS = (
    "kisi_genel_degerlendirme",
    "kisi_davranis_analizi",
    "kisi_ticari_yaklasim",
    "kisi_risk_notlari",
    "kisi_etiketleri",
)


@dataclass(slots=True)
class ContactIntelligenceOutput:
    profile_type: str
    communication_tone: str
    decision_style: str
    negotiation_level: str
    risk_score: int
    relationship_strength: str
    recommended_action: str


def analyze_contact_intelligence(data: dict[str, str]) -> ContactIntelligenceOutput:
    normalized_text = _normalize_text(
        " ".join(str(data.get(key, "") or "") for key in INTELLIGENCE_KEYS)
    )

    output = ContactIntelligenceOutput(
        profile_type="Standart",
        communication_tone="Dengeli",
        decision_style="Orta",
        negotiation_level="Normal",
        risk_score=0,
        relationship_strength="Orta",
        recommended_action="İlişkiyi derinleştir",
    )

    if "pazarlik" in normalized_text:
        output.profile_type = "Pazarlıkçı"
    elif "hizli" in normalized_text:
        output.profile_type = "Hızlı Karar Verici"
    elif "detay" in normalized_text or "analitik" in normalized_text:
        output.profile_type = "Analitik"

    if "teknik" in normalized_text or "detay" in normalized_text:
        output.communication_tone = "Teknik ve Detaylı"
    elif "samimi" in normalized_text:
        output.communication_tone = "Samimi"

    if "yavas" in normalized_text:
        output.decision_style = "Yavaş"
    elif "hizli" in normalized_text:
        output.decision_style = "Hızlı"

    if "fiyat hassas" in normalized_text or "pazarlik" in normalized_text:
        output.negotiation_level = "Yüksek"

    risk = 0
    if "zor" in normalized_text:
        risk += 30
    if "geciktirir" in normalized_text:
        risk += 20
    if "kararsiz" in normalized_text:
        risk += 20
    output.risk_score = min(risk, 100)

    if "guven" in normalized_text or "iyi iliski" in normalized_text:
        output.relationship_strength = "Güçlü"
    elif "yeni" in normalized_text:
        output.relationship_strength = "Zayıf"

    if output.risk_score > 50:
        output.recommended_action = "Teması yumuşat, direkt satış yapma"
    elif output.negotiation_level == "Yüksek":
        output.recommended_action = "Fiyat stratejisi ile ilerle"
    elif output.decision_style == "Hızlı":
        output.recommended_action = "Hızlı teklif ver ve kapatmaya çalış"

    return output


def has_contact_intelligence_data(data: dict[str, str]) -> bool:
    return any(str(data.get(key, "") or "").strip() for key in INTELLIGENCE_KEYS)


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return normalized.lower()
