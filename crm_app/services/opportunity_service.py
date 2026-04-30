from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from crm_app.database.session import get_session
from crm_app.models import Company, Contact, Opportunity


PIPELINE_STAGES = [
    "Yeni Lead",
    "Araştırılıyor",
    "İlk Temas Yapıldı",
    "Cevap Bekleniyor",
    "Görüşme Yapıldı",
    "Numune Gönderildi",
    "Teklif Verildi",
    "Takipte",
    "Kazanıldı",
    "Kaybedildi",
    "Pasif",
]
ACTIVE_CLOSED_STAGES = {"Kazanıldı", "Kaybedildi", "Pasif"}
PIPELINE_SUMMARY_STAGES = [
    "Yeni Lead",
    "İlk Temas Yapıldı",
    "Numune Gönderildi",
    "Teklif Verildi",
    "Takipte",
    "Kazanıldı",
    "Kaybedildi",
]


def list_opportunities(
    search_text: str = "",
    stage: str = "",
    company_id: int | None = None,
    currency: str = "",
) -> list[Opportunity]:
    with get_session() as session:
        query = (
            select(Opportunity)
            .join(Opportunity.company)
            .join(Opportunity.contact, isouter=True)
            .options(joinedload(Opportunity.company), joinedload(Opportunity.contact))
            .order_by(
                Opportunity.expected_close_date.is_(None),
                Opportunity.expected_close_date.asc(),
                Opportunity.updated_at.desc(),
            )
        )

        if search_text:
            term = f"%{search_text.lower()}%"
            query = query.where(
                func.lower(func.coalesce(Opportunity.title, "")).like(term)
                | func.lower(func.coalesce(Opportunity.note, "")).like(term)
                | func.lower(func.coalesce(Company.name, "")).like(term)
                | func.lower(func.coalesce(Contact.name, "")).like(term)
            )

        if stage:
            query = query.where(Opportunity.stage == stage)

        if company_id:
            query = query.where(Opportunity.company_id == company_id)

        if currency:
            query = query.where(Opportunity.currency == currency)

        return list(session.scalars(query).unique())


def get_opportunity(opportunity_id: int) -> Opportunity | None:
    with get_session() as session:
        query = (
            select(Opportunity)
            .options(joinedload(Opportunity.company), joinedload(Opportunity.contact))
            .where(Opportunity.id == opportunity_id)
        )
        return session.scalars(query).first()


def create_opportunity(data: dict[str, Any]) -> Opportunity:
    with get_session() as session:
        opportunity = Opportunity(**data)
        session.add(opportunity)
        session.commit()
        session.refresh(opportunity)
        return opportunity


def update_opportunity(opportunity_id: int, data: dict[str, Any]) -> None:
    with get_session() as session:
        opportunity = session.get(Opportunity, opportunity_id)
        if not opportunity:
            return

        for field, value in data.items():
            setattr(opportunity, field, value)

        session.commit()


def delete_opportunity(opportunity_id: int) -> None:
    with get_session() as session:
        opportunity = session.get(Opportunity, opportunity_id)
        if not opportunity:
            return

        session.delete(opportunity)
        session.commit()


def list_opportunity_stages() -> list[str]:
    return PIPELINE_STAGES.copy()


def list_opportunity_currencies() -> list[str]:
    base_currencies = ["EUR", "USD", "TRY"]
    with get_session() as session:
        query = (
            select(Opportunity.currency)
            .where(Opportunity.currency.is_not(None), Opportunity.currency != "")
            .distinct()
            .order_by(Opportunity.currency.asc())
        )
        dynamic = [value for value in session.scalars(query) if value]

    return base_currencies + [value for value in dynamic if value not in base_currencies]


def get_opportunity_summary() -> dict[str, int]:
    active_stages = [stage for stage in PIPELINE_STAGES if stage not in ACTIVE_CLOSED_STAGES]
    with get_session() as session:
        active_count = (
            session.scalar(
                select(func.count()).select_from(Opportunity).where(Opportunity.stage.in_(active_stages))
            )
            or 0
        )
        active_amount = (
            session.scalar(
                select(func.coalesce(func.sum(Opportunity.expected_amount), 0)).where(
                    Opportunity.stage.in_(active_stages)
                )
            )
            or 0
        )
        teklif_verildi_count = (
            session.scalar(
                select(func.count()).select_from(Opportunity).where(Opportunity.stage == "Teklif Verildi")
            )
            or 0
        )
        won_count = (
            session.scalar(
                select(func.count()).select_from(Opportunity).where(Opportunity.stage == "Kazanıldı")
            )
            or 0
        )
        lost_count = (
            session.scalar(
                select(func.count()).select_from(Opportunity).where(Opportunity.stage == "Kaybedildi")
            )
            or 0
        )

    return {
        "active_opportunities": active_count,
        "active_amount": int(active_amount or 0),
        "teklif_verildi_count": teklif_verildi_count,
        "won_count": won_count,
        "lost_count": lost_count,
    }


def get_pipeline_stage_counts(stages: list[str] | None = None) -> list[tuple[str, int]]:
    target_stages = stages or PIPELINE_SUMMARY_STAGES
    with get_session() as session:
        query = (
            select(Opportunity.stage, func.count())
            .where(Opportunity.stage.in_(target_stages))
            .group_by(Opportunity.stage)
        )
        counts = {stage: count for stage, count in session.execute(query).all()}

    return [(stage, counts.get(stage, 0)) for stage in target_stages]


def find_related_open_opportunity(
    company_id: int,
    contact_id: int | None = None,
) -> Opportunity | None:
    with get_session() as session:
        query = (
            select(Opportunity)
            .options(joinedload(Opportunity.company), joinedload(Opportunity.contact))
            .where(
                Opportunity.company_id == company_id,
                ~Opportunity.stage.in_(ACTIVE_CLOSED_STAGES),
            )
            .order_by(Opportunity.updated_at.desc())
        )
        opportunities = list(session.scalars(query).unique())

    if contact_id is not None:
        for opportunity in opportunities:
            if opportunity.contact_id == contact_id:
                return opportunity
    return opportunities[0] if opportunities else None


def list_stale_quoted_opportunities(days: int = 14) -> list[Opportunity]:
    cutoff = datetime.utcnow() - timedelta(days=days)
    with get_session() as session:
        query = (
            select(Opportunity)
            .options(joinedload(Opportunity.company), joinedload(Opportunity.contact))
            .where(
                Opportunity.stage == "Teklif Verildi",
                Opportunity.updated_at <= cutoff,
            )
            .order_by(Opportunity.updated_at.asc())
        )
        return list(session.scalars(query).unique())
