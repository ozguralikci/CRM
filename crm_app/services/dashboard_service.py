from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from crm_app.database.session import get_session
from crm_app.models import Action, Company, Contact
from crm_app.services.offer_service import get_offer_summary
from crm_app.services.opportunity_service import get_opportunity_summary, get_pipeline_stage_counts
from crm_app.services.sample_service import get_sample_status_counts, get_sample_summary


def get_dashboard_metrics() -> dict[str, int]:
    today = date.today()

    with get_session() as session:
        total_companies = session.scalar(select(func.count()).select_from(Company)) or 0
        total_contacts = session.scalar(select(func.count()).select_from(Contact)) or 0
        todays_actions = (
            session.scalar(
                select(func.count())
                .select_from(Action)
                .where(func.date(Action.created_at) == today.isoformat())
            )
            or 0
        )
        delayed_actions = (
            session.scalar(
                select(func.count())
                .select_from(Action)
                .where(Action.next_action_date.is_not(None), Action.next_action_date < today)
            )
            or 0
        )
        high_priority_companies = (
            session.scalar(
                select(func.count()).select_from(Company).where(Company.priority >= 4)
            )
            or 0
        )

    return {
        "total_companies": total_companies,
        "total_contacts": total_contacts,
        "todays_actions": todays_actions,
        "delayed_actions": delayed_actions,
        "high_priority_companies": high_priority_companies,
    }


def list_todays_followups(limit: int = 8) -> list[Action]:
    today = date.today()
    with get_session() as session:
        query = (
            select(Action)
            .options(joinedload(Action.company), joinedload(Action.contact))
            .where(Action.next_action_date == today)
            .order_by(Action.created_at.desc())
            .limit(limit)
        )
        return list(session.scalars(query).unique())


def list_overdue_actions(limit: int = 8) -> list[Action]:
    today = date.today()
    with get_session() as session:
        query = (
            select(Action)
            .options(joinedload(Action.company), joinedload(Action.contact))
            .where(Action.next_action_date.is_not(None), Action.next_action_date < today)
            .order_by(Action.next_action_date.asc(), Action.created_at.desc())
            .limit(limit)
        )
        return list(session.scalars(query).unique())


def list_hot_companies(limit: int = 8) -> list[Company]:
    with get_session() as session:
        query = (
            select(Company)
            .where(Company.priority >= 4)
            .order_by(Company.priority.desc(), Company.created_at.desc())
            .limit(limit)
        )
        return list(session.scalars(query))


def list_recent_actions(limit: int = 5) -> list[Action]:
    with get_session() as session:
        query = (
            select(Action)
            .options(joinedload(Action.company), joinedload(Action.contact))
            .order_by(Action.created_at.desc())
            .limit(limit)
        )
        return list(session.scalars(query).unique())


def get_commercial_metrics() -> dict[str, int]:
    opportunity_metrics = get_opportunity_summary()
    offer_metrics = get_offer_summary()
    sample_metrics = get_sample_summary()

    return {
        "active_opportunities": opportunity_metrics["active_opportunities"],
        "active_amount": opportunity_metrics["active_amount"],
        "teklif_verildi_count": opportunity_metrics["teklif_verildi_count"],
        "won_count": opportunity_metrics["won_count"],
        "lost_count": opportunity_metrics["lost_count"],
        "waiting_offers": offer_metrics["waiting_offers"],
        "accepted_offers": offer_metrics["accepted_offers"],
        "testing_samples": sample_metrics["testing_samples"],
    }


def get_pipeline_summary() -> list[tuple[str, int]]:
    return get_pipeline_stage_counts()


def get_sample_status_summary() -> list[tuple[str, int]]:
    return get_sample_status_counts()
