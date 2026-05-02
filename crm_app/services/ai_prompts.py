"""Araştırma hedefi için AI promptları (FAZ 3C-B / 3D / web tabanlı çıkarım)."""

from __future__ import annotations

from crm_app.models.research_target import ResearchTarget

# Web / firma adı metninde aranan endüstriyel ipuçları (küçük harf eşleşme)
_INDUSTRY_KEYWORD_HINTS: tuple[tuple[str, str], ...] = (
    ("entegre", "entegre sistem veya tesis"),
    ("panel", "elektrik paneli / kabin"),
    ("makina", "makine imalatı"),
    ("makine", "makine imalatı"),
    ("otomotiv", "otomotiv veya taşıt ekipmanı"),
    ("hidrolik", "hidrolik / pnömatik"),
    ("pnomatik", "pnömatik"),
    ("pnömatik", "pnömatik"),
    ("kimya", "kimya veya proses endüstrisi"),
    ("hydraulic", "hidrolik"),
    ("automotive", "otomotiv"),
)


def _clip(text: str, max_len: int) -> str:
    t = (text or "").strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 1].rstrip() + "…"


def get_website_keyword_labels(target: ResearchTarget) -> list[str]:
    """Web + firma adında tanımlı endüstriyel anahtar sözcük etiketleri (boş olabilir)."""
    return _keyword_hint_lines(target.website or "", target.name or "")


def _keyword_hint_lines(website: str, company_name: str) -> list[str]:
    blob = f"{(website or '').lower()} {(company_name or '').lower()}"
    labels: list[str] = []
    for kw, label in _INDUSTRY_KEYWORD_HINTS:
        if kw in blob and label not in labels:
            labels.append(label)
    return labels


def build_research_target_ai_messages(target: ResearchTarget, max_chars: int = 2000) -> list[dict[str, str]]:
    """
    Panel «AI Analiz Et» için system + user mesajları.
    User bloğu toplam uzunluğu max_chars'ı aşmamalı.
    """
    system = (
        "Sen Sürlas (kauçuk conta, O-ring, teknik kauçuk parça, sızdırmazlık) için "
        "endüstriyel B2B satış analisti olarak çalışıyorsun. "
        "Genel pazarlama cümlesi yazma; teknik ve satış dilinde, somut öneriler üret. "
        "Kanıt zayıfsa alanı boş veya yalnızca 'belirsiz' bırakma: "
        "web adresi, firma adı veya kayıtlı metin ipucu veriyorsa düşük güvenli teknik tahmin yap; "
        "tahminleri 'tahmini:' ile başlat ve güven seviyesini kısaca belirt. "
        "Kesin satış garantisi veya yasal iddia yok; uydurma somut sipariş/figür yok. "
        "Çıktı yalnızca tek bir JSON nesnesi; şemadaki tüm anahtarlar zorunlu; markdown yok. "
        "decision yalnızca: TAKİP ET, BEKLET, ELE, belirsiz. "
        "fit_score_percent 0–100 tamsayı; kanıt zayıfsa düşük skor, karar alanını gerekçeyle doldur. "
        "WEB SİTESİ DOLU İSE: sector alanını boş veya yalnızca 'belirsiz' bırakma — "
        "domain ve genel sektör bilgisiyle tahmini sektör yaz. "
        "Üretim / montaj olasılığı yüksek görünüyorsa technical_usage alanında "
        "yalnızca 'belirsiz' yazma; makine, hat, bağlantı veya proses düzeyinde tahmini kullanım yaz."
    )

    parts: list[str] = [
        "Kaydı endüstriyel kullanım (makine/proses), sızdırmazlık, Sürlas ürün uyumu, "
        "satış zorluğu ve portföy kararı açısından analiz et. Özet kısa ve teknik olsun.",
        "",
        f"Firma adı: {_clip(target.name or '', 400)}",
        f"Web sitesi: {_clip(target.website or '', 300)}",
        f"LinkedIn (şirket): {_clip(target.linkedin_company_url or '', 300)}",
        f"Ülke: {_clip(target.country or '', 120)}",
        f"Şehir: {_clip(target.city or '', 120)}",
        f"Sektör (kayıt): {_clip(target.sector or '', 200)}",
        f"Firma tipi: {_clip(target.company_type or '', 120)}",
        f"Üretim yapısı: {_clip(target.production_structure or '', 200)}",
        f"Ürün uyumu sinyalleri: {_clip(target.product_fit_signals or '', 600)}",
        f"Notlar: {_clip(target.notes or '', 600)}",
    ]

    if (target.website or "").strip():
        hits = _keyword_hint_lines(target.website or "", target.name or "")
        parts.append("")
        parts.append(
            "WEB SİTESİ MEVCUT: Domain ve yukarıdaki metinlerden endüstriyel sektör, "
            "üretim tipi ve olası sızdırmazlık senaryolarını düşük güvenle çıkar; "
            "sector ve technical_usage için anlamlı tahmin yaz (yalnızca 'belirsiz' ile geçme)."
        )
        if hits:
            parts.append(
                "Otomatik anahtar sözcük ipuçları (model bunları dikkate alsın): "
                + ", ".join(hits)
                + " → sektör, production_structure, sealing_need / sealing_where ve technical_usage "
                "ile hizala; her tahmini 'tahmini:' ile etiketle."
            )

    user_body = "\n".join(parts).strip()
    user_body = _clip(user_body, max_chars)

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_body},
    ]
