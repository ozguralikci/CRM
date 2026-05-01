from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import func, select

from crm_app.database.session import get_session
from crm_app.models.research_target import ResearchTarget


def _normalize_name(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def _normalize_domain(website: str) -> str:
    raw = (website or "").strip().lower()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    try:
        netloc = urlparse(raw).netloc.lower()
    except ValueError:
        return ""
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def _normalize_linkedin_company(url: str) -> str:
    s = (url or "").strip().lower().rstrip("/")
    if not s:
        return ""
    if "linkedin.com" not in s:
        return s
    # keep path after linkedin.com for duplicate grouping
    m = re.search(r"linkedin\.com/(.+)$", s)
    return m.group(1) if m else s


def basic_duplicate_check(
    *,
    name: str = "",
    website: str = "",
    linkedin_company_url: str = "",
    exclude_id: int | None = None,
) -> list[ResearchTarget]:
    name_key = _normalize_name(name)
    domain_key = _normalize_domain(website)
    li_key = _normalize_linkedin_company(linkedin_company_url)

    with get_session() as session:
        candidates = list(session.scalars(select(ResearchTarget)).all())
        matches: list[ResearchTarget] = []
        seen: set[int] = set()

        for t in candidates:
            if exclude_id is not None and t.id == exclude_id:
                continue
            hit = False
            if name_key and _normalize_name(t.name) == name_key:
                hit = True
            if domain_key and _normalize_domain(t.website) == domain_key:
                hit = True
            if li_key and _normalize_linkedin_company(t.linkedin_company_url) == li_key:
                hit = True
            if hit and t.id not in seen:
                seen.add(t.id)
                matches.append(t)

        return matches


def create_research_target(data: dict[str, Any]) -> ResearchTarget:
    payload = dict(data)
    with get_session() as session:
        target = ResearchTarget(**payload)
        session.add(target)
        session.commit()
        session.refresh(target)
        return target


def get_research_target(target_id: int) -> ResearchTarget | None:
    with get_session() as session:
        return session.get(ResearchTarget, target_id)


def list_research_targets(
    *,
    search: str = "",
    status: str = "",
    country: str = "",
    sector: str = "",
) -> list[ResearchTarget]:
    with get_session() as session:
        q = select(ResearchTarget).order_by(ResearchTarget.updated_at.desc())
        if status:
            q = q.where(ResearchTarget.status == status)
        if country:
            term = f"%{country.strip().lower()}%"
            q = q.where(func.lower(ResearchTarget.country).like(term))
        if sector:
            term = f"%{sector.strip().lower()}%"
            q = q.where(func.lower(ResearchTarget.sector).like(term))
        if search:
            term = f"%{search.strip().lower()}%"
            q = q.where(
                func.lower(ResearchTarget.name).like(term)
                | func.lower(ResearchTarget.city).like(term)
                | func.lower(ResearchTarget.website).like(term)
                | func.lower(ResearchTarget.linkedin_company_url).like(term)
            )
        return list(session.scalars(q).unique().all())


def update_research_target(target_id: int, data: dict[str, Any]) -> None:
    payload = dict(data)
    with get_session() as session:
        target = session.get(ResearchTarget, target_id)
        if not target:
            return
        for field, value in payload.items():
            setattr(target, field, value)
        session.commit()
