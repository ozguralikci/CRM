from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover - pip install PyYAML
    raise ImportError("surlas_scoring_v1 requires PyYAML; pip install PyYAML") from exc


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def load_scoring_config(path: Path | str | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else _project_root() / "config" / "surlas_scoring_v1.yaml"
    raw = cfg_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid scoring config: {cfg_path}")
    return data


def _get_field(target: Any, key: str, default: str = "") -> str:
    if isinstance(target, Mapping):
        val = target.get(key, default)
    else:
        val = getattr(target, key, default)
    if val is None:
        return default
    return str(val).strip()


def _normalize_match_blob(*parts: str) -> str:
    blob = " ".join(p.lower().strip() for p in parts if p)
    repl = str.maketrans("ıİşğüöçŞĞÜÖÇ", "iisguocsguoc")
    return blob.translate(repl)


def score_sector_match(target: Any, config: dict[str, Any]) -> dict[str, Any]:
    weights = config.get("weights") or {}
    sector_max = int(weights.get("sector_max", 25))
    sector_text = _normalize_match_blob(_get_field(target, "sector"))
    sec_cfg = config.get("sector") or {}

    breakdown: dict[str, Any] = {
        "max": sector_max,
        "raw_sector": _get_field(target, "sector"),
        "matched_tier": None,
        "matched_pattern": None,
        "points": 0,
        "exclude_hit": False,
        "cap_final_score": None,
    }

    # Önce exclude
    for rule in sec_cfg.get("exclude") or []:
        patterns = rule.get("patterns") or []
        for p in patterns:
            pn = _normalize_match_blob(p)
            if pn and pn in sector_text:
                breakdown["exclude_hit"] = True
                breakdown["matched_tier"] = "exclude"
                breakdown["matched_pattern"] = p
                breakdown["points"] = int(rule.get("points_override", 0))
                cap = rule.get("cap_final_score")
                breakdown["cap_final_score"] = int(cap) if cap is not None else None
                return breakdown

    best_points = 0
    best_tier = None
    best_pat = None

    def scan(tier_name: str, rules: list[Any]) -> None:
        nonlocal best_points, best_tier, best_pat
        for rule in rules:
            pts = int(rule.get("points") or rule.get("points_override") or 0)
            for p in rule.get("patterns") or []:
                pn = _normalize_match_blob(p)
                if pn and pn in sector_text and pts > best_points:
                    best_points = pts
                    best_tier = tier_name
                    best_pat = p

    scan("primary", sec_cfg.get("primary") or [])
    scan("secondary", sec_cfg.get("secondary") or [])
    scan("adjacent", sec_cfg.get("adjacent") or [])

    breakdown["points"] = min(best_points, sector_max)
    breakdown["matched_tier"] = best_tier
    breakdown["matched_pattern"] = best_pat
    return breakdown


def score_product_signals(target: Any, config: dict[str, Any]) -> dict[str, Any]:
    weights = config.get("weights") or {}
    product_max = int(weights.get("product_max", 35))
    ps_cfg = config.get("product_signals") or {}

    text = _normalize_match_blob(
        _get_field(target, "product_fit_signals"),
        _get_field(target, "notes"),
    )

    detail: dict[str, Any] = {
        "max": product_max,
        "positive_points": 0,
        "groups": [],
        "negative_hits": [],
        "negative_subtract": 0,
    }

    positive_total = 0
    for grp in ps_cfg.get("positive_groups") or []:
        gid = grp.get("id", "?")
        cap = int(grp.get("max_points", 0))
        earned = 0
        matched_kw: list[str] = []
        for kw in grp.get("keywords") or []:
            kn = _normalize_match_blob(kw)
            if kn and kn in text:
                matched_kw.append(kw)
                earned = cap  # grup içinde bir kez tetiklenince tam grup puanı
                break
        earned = min(earned, cap)
        positive_total += earned
        detail["groups"].append({"id": gid, "points": earned, "keywords_hit": matched_kw})

    neg_sub = 0
    for neg in ps_cfg.get("negative_keywords") or []:
        kw = neg.get("kw", "")
        sub = int(neg.get("subtract", 0))
        kn = _normalize_match_blob(kw)
        if kn and kn in text:
            detail["negative_hits"].append(kw)
            neg_sub += sub

    detail["negative_subtract"] = neg_sub
    detail["positive_points"] = min(positive_total, product_max)
    raw = detail["positive_points"] - neg_sub
    detail["points_before_cap"] = raw
    detail["points"] = max(0, min(raw, product_max))
    return detail


def score_operational_fields(target: Any, config: dict[str, Any]) -> dict[str, Any]:
    weights = config.get("weights") or {}
    op_max = int(weights.get("operational_max", 20))
    op_cfg = config.get("operational") or {}

    ctype = _normalize_match_blob(_get_field(target, "company_type"))
    prod = _normalize_match_blob(_get_field(target, "production_structure"))
    country = _normalize_match_blob(_get_field(target, "country"))

    detail: dict[str, Any] = {"max": op_max, "points": 0, "matched": []}
    earned = 0

    for rule in op_cfg.get("company_type_bonus") or []:
        pts = int(rule.get("points", 0))
        for p in rule.get("patterns") or []:
            pn = _normalize_match_blob(p)
            if pn and pn in ctype:
                if pts > earned:
                    earned = pts
                    detail["matched"] = [{"type": "company_type", "pattern": p, "points": pts}]
                break

    prod_pts = 0
    best_prod_pat = None
    for rule in op_cfg.get("production_bonus") or []:
        pts = int(rule.get("points", 0))
        for p in rule.get("patterns") or []:
            pn = _normalize_match_blob(p)
            if pn and pn in prod and pts > prod_pts:
                prod_pts = pts
                best_prod_pat = p

    if prod_pts:
        detail["matched"].append({"type": "production_structure", "pattern": best_prod_pat, "points": prod_pts})

    tier1_keywords = op_cfg.get("country_tier1_keywords") or []
    tier_pts = int(op_cfg.get("country_tier1_points", 0))
    default_c = int(op_cfg.get("default_country_points", 0))
    country_pts = default_c if country else 0
    if country:
        for k in tier1_keywords:
            kn = _normalize_match_blob(str(k))
            if kn and kn in country:
                country_pts = tier_pts
                detail["matched"].append({"type": "country", "pattern": k, "points": country_pts})
                break
        else:
            detail["matched"].append({"type": "country", "pattern": "(default)", "points": country_pts})

    total = earned + prod_pts + country_pts
    detail["points"] = min(total, op_max)
    return detail


def score_evidence_completeness(target: Any, config: dict[str, Any]) -> dict[str, Any]:
    weights = config.get("weights") or {}
    ev_max = int(weights.get("evidence_max", 20))
    ev_cfg = config.get("evidence") or {}
    ps_cfg = config.get("product_signals") or {}

    website = _get_field(target, "website")
    li = _get_field(target, "linkedin_company_url")
    sector = _get_field(target, "sector")
    signals = _get_field(target, "product_fit_signals")
    notes = _get_field(target, "notes")

    pts = 0
    items: list[dict[str, Any]] = []

    wp = int(ev_cfg.get("website_points", 0))
    if website:
        pts += wp
        items.append({"field": "website", "points": wp})

    lp = int(ev_cfg.get("linkedin_points", 0))
    if li:
        pts += lp
        items.append({"field": "linkedin_company_url", "points": lp})

    sp = int(ev_cfg.get("sector_field_points", 0))
    if sector:
        pts += sp
        items.append({"field": "sector", "points": sp})

    min_sub = int(ps_cfg.get("min_chars_substantial", 40))
    sig_pts = int(ev_cfg.get("signals_substantial_points", 0))
    if len(signals) >= min_sub:
        pts += sig_pts
        items.append({"field": "product_fit_signals_substantial", "points": sig_pts})

    notes_min = int(ev_cfg.get("notes_min_chars", 0))
    nb = int(ev_cfg.get("notes_bonus_points", 0))
    if len(notes) >= notes_min:
        pts += nb
        items.append({"field": "notes_bonus", "points": nb})

    return {"max": ev_max, "points": min(pts, ev_max), "items": items}


def apply_missing_data_penalties(target: Any, config: dict[str, Any]) -> dict[str, Any]:
    pen_cfg = config.get("penalties") or {}
    ps_cfg = config.get("product_signals") or {}

    website = _get_field(target, "website")
    sector_f = _get_field(target, "sector")
    signals = _get_field(target, "product_fit_signals")
    thin_thr = int(ps_cfg.get("thin_char_threshold", 12))

    applied: list[dict[str, Any]] = []
    total = 0

    mw = int(pen_cfg.get("missing_website", 0))
    if not website:
        applied.append({"code": "missing_website", "points": mw})
        total += mw

    ms = int(pen_cfg.get("missing_sector", 0))
    if not sector_f:
        applied.append({"code": "missing_sector", "points": ms})
        total += ms

    mst = int(pen_cfg.get("missing_signals_or_thin", 0))
    if not signals or len(signals) < thin_thr:
        applied.append({"code": "missing_or_thin_signals", "points": mst})
        total += mst

    critical_missing_count = sum(
        1
        for code in (
            not website,
            not sector_f,
            not signals or len(signals) < thin_thr,
        )
        if code
    )
    bundle_extra = int(pen_cfg.get("bundle_extra_when_two_of_three_critical_missing", 0))
    if critical_missing_count >= 2:
        applied.append({"code": "critical_bundle_2of3", "points": bundle_extra})
        total += bundle_extra

    max_pen = int(pen_cfg.get("max_total_penalty", 999))
    capped_total = min(total, max_pen)

    return {
        "lines": applied,
        "raw_total": total,
        "capped_total": capped_total,
        "max_total_penalty": max_pen,
        "critical_missing_count": critical_missing_count,
    }


def compute_fit_score(target: Any, config: dict[str, Any]) -> dict[str, Any]:
    weights = config.get("weights") or {}
    sector_max = int(weights.get("sector_max", 25))
    product_max = int(weights.get("product_max", 35))
    operational_max = int(weights.get("operational_max", 20))
    evidence_max = int(weights.get("evidence_max", 20))

    sector_br = score_sector_match(target, config)
    prod_br = score_product_signals(target, config)
    op_br = score_operational_fields(target, config)
    ev_br = score_evidence_completeness(target, config)
    pen_br = apply_missing_data_penalties(target, config)

    sector_pts = min(int(sector_br.get("points", 0)), sector_max)
    prod_pts = min(int(prod_br.get("points", 0)), product_max)
    op_pts = min(int(op_br.get("points", 0)), operational_max)
    ev_pts = min(int(ev_br.get("points", 0)), evidence_max)

    raw_sum = sector_pts + prod_pts + op_pts + ev_pts
    penalty = int(pen_br.get("capped_total", 0))
    after_pen = raw_sum - penalty

    caps_applied: list[Any] = []
    exclude_cap = sector_br.get("cap_final_score")
    if sector_br.get("exclude_hit") and exclude_cap is not None:
        caps_applied.append({"reason": "sector_exclude", "cap": int(exclude_cap)})

    pen_cfg = config.get("penalties") or {}
    bundle_cap = pen_cfg.get("score_cap_when_critical_bundle")
    if pen_br.get("critical_missing_count", 0) >= 2 and bundle_cap is not None:
        caps_applied.append({"reason": "critical_data_bundle", "cap": int(bundle_cap)})

    score = max(0, min(100, after_pen))
    for cap_info in caps_applied:
        score = min(score, int(cap_info["cap"]))

    # Güven: eksik kritik alan ve exclude ile düşer
    confidence = 88
    if pen_br.get("critical_missing_count", 0) >= 2:
        confidence -= 28
    elif pen_br.get("critical_missing_count", 0) == 1:
        confidence -= 14
    if sector_br.get("exclude_hit"):
        confidence -= 22
    if not _get_field(target, "website"):
        confidence -= 10
    confidence = max(12, min(100, confidence))

    cat_cfg = config.get("categories") or {}
    w_max = int(cat_cfg.get("weak_max", 39))
    m_max = int(cat_cfg.get("medium_max", 54))
    g_max = int(cat_cfg.get("good_max", 74))

    if score <= w_max:
        category = "Zayıf"
    elif score <= m_max:
        category = "Orta"
    elif score <= g_max:
        category = "İyi"
    else:
        category = "Sıcak"

    rec_map = config.get("recommendations") or {}
    recommendation = str(
        rec_map.get(
            {"Zayıf": "weak", "Orta": "medium", "İyi": "good", "Sıcak": "hot"}[category],
            "",
        )
        or "Skoru gözden geçirin."
    )

    breakdown = {
        "ruleset_version": config.get("ruleset_version", "?"),
        "components": {
            "sector": sector_br,
            "product_signals": prod_br,
            "operational": op_br,
            "evidence": ev_br,
        },
        "penalties": pen_br,
        "sums": {
            "raw_components": raw_sum,
            "after_penalties_uncapped_clamped": max(0, min(100, after_pen)),
            "caps_applied": caps_applied,
        },
        "weights_reference": weights,
    }

    return {
        "score": int(score),
        "confidence": int(confidence),
        "breakdown": breakdown,
        "category": category,
        "recommendation": recommendation,
    }


def _demo_targets() -> list[SimpleNamespace]:
    return [
        SimpleNamespace(
            name="ABC Otomotiv Conta A.S.",
            website="https://abcotomotiv.example.com",
            linkedin_company_url="https://linkedin.com/company/abc-otomotiv",
            country="Turkiye",
            city="Bursa",
            sector="Otomotiv yan sanayi — OEM conta ve hidrolik hortum",
            company_type="Uretici",
            production_structure="Montaj hatti ve pres",
            product_fit_signals=(
                "OEM O-ring, hidrolik conta, sizdirmazlik elemanlari; "
                "tier-2 tedarikci, forklift hidrolik hortum ihtiyaci."
            ),
            notes="2025 fuar karti alindi, teknik mudur ile gorusme.",
        ),
        SimpleNamespace(
            name="Beta Makina (web sitesiz)",
            website="",
            linkedin_company_url="",
            country="Turkey",
            city="Konya",
            sector="Imalat ve makina — hidrolik sistemler",
            company_type="tedarikci",
            production_structure="",
            product_fit_signals="Hidrolik silindir ve hortum baglantilari.",
            notes="",
        ),
        SimpleNamespace(
            name="Gamma Yazilim Ltd.",
            website="https://gamma.example.com",
            linkedin_company_url="",
            country="Turkiye",
            city="Istanbul",
            sector="Yazilim ve SaaS cozumleri",
            company_type="",
            production_structure="",
            product_fit_signals="ERP entegrasyon ve mobil uygulama.",
            notes="",
        ),
        SimpleNamespace(
            name="Delta Ltd (minimal kayit)",
            website="",
            linkedin_company_url="",
            country="",
            city="",
            sector="",
            company_type="",
            production_structure="",
            product_fit_signals="",
            notes="",
        ),
        SimpleNamespace(
            name="Epsilon Hydraulics Poland",
            website="https://epsilon-hyd.example.eu",
            linkedin_company_url="https://linkedin.com/company/epsilon-hyd",
            country="Poland",
            city="Wroclaw",
            sector="Hydraulic components manufacturing",
            company_type="Manufacturer",
            production_structure="CNC machining line",
            product_fit_signals=(
                "Hydraulic hose assemblies, fittings, sealing kits for agricultural tractors."
            ),
            notes="Exports to EU OEMs.",
        ),
    ]


def main() -> None:
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except OSError:
            pass

    config = load_scoring_config()
    print("Sürlas scoring FAZ 2A — dry-run demo (DB yazimi yok)\n")
    for i, t in enumerate(_demo_targets(), start=1):
        result = compute_fit_score(t, config)
        print(f"--- Örnek {i}: {t.name} ---")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print()


if __name__ == "__main__":
    main()
