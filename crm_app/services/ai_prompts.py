"""Araştırma hedefi için AI promptları (FAZ 3C-B / 3D)."""

from __future__ import annotations

from crm_app.models.research_target import ResearchTarget


def _clip(text: str, max_len: int) -> str:
    t = (text or "").strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 1].rstrip() + "…"


def build_research_target_ai_messages(target: ResearchTarget, max_chars: int = 2000) -> list[dict[str, str]]:
    """
    Panel «AI Analiz Et» için system + user mesajları.
    User bloğu toplam uzunluğu max_chars'ı aşmamalı.
    """
    system = (
        "Sen Sürlas (kauçuk conta, O-ring, teknik kauçuk parça, sızdırmazlık) için "
        "endüstriyel B2B satış analisti olarak çalışıyorsun. "
        "Genel pazarlama lafı veya belirsiz övgü üretme; teknik ve satış odaklı yaz. "
        "Verilen kayıttaki bilgilerle Sürlas ürün portföyü (conta, O-ring, sızdırmazlık, teknik kauçuk) "
        "arasında somut eşleştirme yap; kanıt yoksa uydurma, alanlarda 'belirsiz' kullan. "
        "Kesin satış garantisi veya yasal iddia yok. "
        "Çıktı yalnızca tek bir JSON nesnesi; şemadaki tüm anahtarlar zorunlu; markdown veya açıklama dışı metin yok. "
        "decision yalnızca şu değerlerden biri: TAKİP ET, BEKLET, ELE, belirsiz. "
        "fit_score_percent 0–100 tamsayı; veriye dayanarak makul tahmin, kanıt yoksa düşük veya belirsiz karar tercih et."
    )

    parts: list[str] = [
        "Kaydı endüstriyel kullanım (makine/proses), sızdırmazlık ihtiyacı, Sürlas ürün uyumu, "
        "satış zorluğu ve portföy kararı açısından analiz et. Özet alanı kısa ve teknik odaklı olsun.",
        "",
        f"Firma adı: {_clip(target.name or '', 400)}",
        f"Web sitesi: {_clip(target.website or '', 300)}",
        f"LinkedIn (şirket): {_clip(target.linkedin_company_url or '', 300)}",
        f"Ülke: {_clip(target.country or '', 120)}",
        f"Şehir: {_clip(target.city or '', 120)}",
        f"Sektör: {_clip(target.sector or '', 200)}",
        f"Firma tipi: {_clip(target.company_type or '', 120)}",
        f"Üretim yapısı: {_clip(target.production_structure or '', 200)}",
        f"Ürün uyumu sinyalleri: {_clip(target.product_fit_signals or '', 600)}",
        f"Notlar: {_clip(target.notes or '', 600)}",
    ]
    user_body = "\n".join(parts).strip()
    user_body = _clip(user_body, max_chars)

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_body},
    ]
