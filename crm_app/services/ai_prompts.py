"""Araştırma hedefi için AI promptları (FAZ 3C-B / 3D / 3F endüstriyel derinlik)."""

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
        "Rollerin: (1) mekanik bakım mühendisi (2) üretim mühendisi (3) endüstriyel teknik satış mühendisi. "
        "Sen Sürlas ürünleri (kauçuk conta, O-ring, hidrolik/statik conta, özel teknik kauçuk, sızdırmazlık) "
        "için B2B analizi üretiyorsun. "
        "Sektör veya tesis tipi tahmin edildiyse, o ortamda sık görülen makine ve prosesleri ismen düşün: "
        "ör. hidrolik pres ve silindirler, kesim hatları, konveyör tambur/bant bağlantıları, pompaj istasyonları, "
        "tozlu veya yüksek sıcaklık hatları, vana ve aktüatör birleşimleri, bakım döngüsü ve aşınma noktaları. "
        "KESİNLİKLE KULLANMA veya bu ifadelerle geçme (anlamsız genelleme): "
        "'proses ekipmanları', 'makine bağlantıları', 'endüstriyel hatlar', 'endüstriyel sistemler', "
        "'endüstriyel hat', 'genel bağlantılar'. "
        "Bunun yerine somut adlar kullan: örn. hidrolik pres silindir strok contası, pompa gövdesi sızdırmazlığı, "
        "vana gövdesi–aktüatör birleşimi, konveyör istasyonu kauçuk tampon/conta, flanş/manşon sızdırmazlığı. "
        "Güven tonu (çıkarım kayıtta doğrudan yazmıyorsa ASLA kesin gerçek gibi yazma): "
        "düşük güven → 'tahmini' veya 'tahmini olarak'; orta güven → 'muhtemel' veya 'yüksek olasılıkla'; "
        "kayıtta açıkça yazılmış teknik bilgi → net cümle kullanılabilir. "
        "KESİN edilgen ve kesin fiil kalıplarından kaçın: 'kullanmaktadır', 'kullanılmaktadır', 'ihtiyaç duyulmaktadır', "
        "'gerekmektedir' (çıkarım için); yerine 'muhtemel olarak kullanılır', 'ihtiyaç olasılığı', 'tahmini olarak öngörülür'. "
        "Çıkarılan makine kullanımını asla doğrulanmış gerçek gibi sunma; somut teknik detayı koru ama epistemik olarak yumuşak tut. "
        "KANIT FARKINDALIĞI: Her teknik çıkarımda neden kısaca yazılmalı. "
        "technical_usage ve sealing_need alanlarının her biri, olasılık cümlesini EN AZ BİR kısa gerekçe ile bitirmelidir: "
        "virgül veya '—' veya 'çünkü' ile tek kısa yan cümle (fazla paragraf yok). "
        "Örnek iyi: '...muhtemeldir, çünkü bu tür üretim hatlarında yüksek basınçlı hidrolik sistemler yaygındır'. "
        "Kötü: sadece 'kullanılır' / gerekçesiz tek iddia. "
        "technical_usage ZORUNLU: en az iki somut makine veya hat türü; çalışma koşulları (sıcaklık, toz, kimyasal) "
        "ve bakım / aşınma riski; çıkarımsa 'tahmini olarak' / 'muhtemel' / 'yüksek olasılıkla' + yukarıdaki kısa gerekçe. "
        "sealing_need ZORUNLU: ihtiyaç/olasılık cümlesi + aynı alan içinde tek kısa gerekçe (kayıt veya sektör tipi). "
        "sealing_where ZORUNLU: en az iki somut nokta (hidrolik silindir, pompa, vana, pres, konveyör, flanş/manşon vb.); "
        "çıkarımsa olasılık dili; istenirse noktaları gerekçeyle birleştir, ama yine kısa tut. "
        "surlas_fit_products: teknik ürün adları (O-ring, hidrolik conta, düz/statik conta, özel teknik kauçuk parça); "
        "gerekirse yüksek sıcaklığa veya kimyasala dayanım, titreşim sönümleme gibi gereksinimleri ayrı öğe olarak yaz. "
        "sales_strategy: önce teknik ihtiyaç keşfi; numune/ölçü/teknik resim talebi; bakım ve tedarik sürekliliği; "
        "arıza ve duruş azaltma vurgusu; fiyat öncesi değer önerisi. "
        "Kanıt zayıfsa alanı boş bırakma: web, firma adı veya kayıt metni ipucu veriyorsa düşük güvenli tahmin yaz. "
        "Kesin satış garantisi veya yasal iddia yok; sipariş no, müşteri adı, rakam uydurma. "
        "Çıktı yalnızca tek JSON nesnesi; şemadaki tüm anahtarlar zorunlu; markdown yok. "
        "decision: TAKİP ET, BEKLET, ELE, belirsiz. fit_score_percent 0–100 tamsayı. "
        "WEB SİTESİ DOLU İSE: sector yalnızca 'belirsiz' olamaz; domain ve bilinen sektör bilgisiyle tahmini sektör yaz."
    )

    parts: list[str] = [
        "Kaydı makine parkı, proses hatları, sızdırmazlık noktaları ve Sürlas ürün eşlemesi üzerinden analiz et. "
        "Özet: kısa, teknik, somut fiil ve ekipman adları içersin.",
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
        "",
        "Alan kuralları (metin içinde yerine getir):",
        "- technical_usage: somut makine/hat + ortam + bakım-aşınma; her ana çıkarım satırının sonunda tek kısa 'çünkü/—' gerekçesi.",
        "- sealing_need: ihtiyaç/olasılık + tek kısa gerekçe (kayıt veya sektör ortamına atıf); uzun açıklama yok.",
        "- sealing_where: en az iki somut sızdırmazlık yeri; kesin iddia yok; mümkünse kısa gerekçe ile bağla.",
        "- surlas_fit_products: Sürlas tipi ürünler, teknik sıfatlar mümkünse ayrı liste öğesi; uygunluğu olasılıkla bağla.",
        "- sales_strategy: keşif → numune/resim → süreklilik/arıza azaltma sırası; öneri dili, emir kipi değil.",
    ]

    if (target.website or "").strip():
        hits = _keyword_hint_lines(target.website or "", target.name or "")
        parts.append("")
        parts.append(
            "WEB SİTESİ MEVCUT: Domain ve metinlerden sektör ve üretim tipi çıkar; "
            "technical_usage ve sealing_where alanlarını web ipucu ile zenginleştir."
        )
        if hits:
            parts.append(
                "Anahtar sözcük ipuçları: "
                + ", ".join(hits)
                + " — tahminleri bu ipuçlarıyla hizala; güven düşükse 'tahmini olarak', orta ise 'muhtemel' kullan."
            )

    user_body = "\n".join(parts).strip()
    user_body = _clip(user_body, max_chars)

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_body},
    ]
