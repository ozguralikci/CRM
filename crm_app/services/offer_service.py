from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from crm_app.database.session import get_session
from crm_app.models import Company, Contact, Offer

PENDING_OFFER_STATUSES = ["Hazirlaniyor", "Gonderildi", "Gorusuluyor", "Revize Edildi"]


def split_offer_note(note: str) -> tuple[str, str]:
    if not note:
        return "", ""

    parts = note.split("\n\n", 1)
    description = parts[0].strip()
    details = parts[1].strip() if len(parts) > 1 else ""
    return description, details


def merge_offer_note(description: str, details: str) -> str:
    description = description.strip()
    details = details.strip()
    if description and details:
        return f"{description}\n\n{details}"
    return description or details


def list_offers(
    search_text: str = "",
    status: str = "",
    currency: str = "",
    company_id: int | None = None,
) -> list[Offer]:
    with get_session() as session:
        query = (
            select(Offer)
            .join(Offer.company)
            .join(Offer.contact, isouter=True)
            .options(joinedload(Offer.company), joinedload(Offer.contact))
            .order_by(Offer.date.is_(None), Offer.date.desc(), Offer.id.desc())
        )

        if search_text:
            term = f"%{search_text.lower()}%"
            query = query.where(
                func.lower(func.coalesce(Offer.offer_no, "")).like(term)
                | func.lower(func.coalesce(Offer.note, "")).like(term)
                | func.lower(func.coalesce(Offer.file_path, "")).like(term)
                | func.lower(func.coalesce(Company.name, "")).like(term)
                | func.lower(func.coalesce(Contact.name, "")).like(term)
            )

        if status:
            query = query.where(Offer.status == status)

        if currency:
            query = query.where(Offer.currency == currency)

        if company_id:
            query = query.where(Offer.company_id == company_id)

        return list(session.scalars(query).unique())


def get_offer(offer_id: int) -> Offer | None:
    with get_session() as session:
        query = (
            select(Offer)
            .options(joinedload(Offer.company), joinedload(Offer.contact))
            .where(Offer.id == offer_id)
        )
        return session.scalars(query).first()


def create_offer(data: dict[str, Any]) -> Offer:
    payload = dict(data)
    if not payload.get("offer_no"):
        payload["offer_no"] = generate_offer_no()

    with get_session() as session:
        offer = Offer(**payload)
        session.add(offer)
        session.commit()
        session.refresh(offer)
        return offer


def update_offer(offer_id: int, data: dict[str, Any]) -> None:
    payload = dict(data)
    if not payload.get("offer_no"):
        payload["offer_no"] = generate_offer_no()

    with get_session() as session:
        offer = session.get(Offer, offer_id)
        if not offer:
            return

        for field, value in payload.items():
            setattr(offer, field, value)

        session.commit()


def delete_offer(offer_id: int) -> None:
    with get_session() as session:
        offer = session.get(Offer, offer_id)
        if not offer:
            return

        session.delete(offer)
        session.commit()


def generate_offer_no() -> str:
    today = datetime.now()
    prefix = today.strftime("TKL-%Y%m")

    with get_session() as session:
        count = (
            session.scalar(
                select(func.count())
                .select_from(Offer)
                .where(Offer.offer_no.like(f"{prefix}-%"))
            )
            or 0
        )

    return f"{prefix}-{count + 1:03d}"


def list_offer_statuses() -> list[str]:
    base_statuses = [
        "Hazirlaniyor",
        "Gonderildi",
        "Gorusuluyor",
        "Revize Edildi",
        "Kabul Edildi",
        "Reddedildi",
    ]
    with get_session() as session:
        query = (
            select(Offer.status)
            .where(Offer.status.is_not(None), Offer.status != "")
            .distinct()
            .order_by(Offer.status.asc())
        )
        dynamic = [value for value in session.scalars(query) if value]

    return base_statuses + [value for value in dynamic if value not in base_statuses]


def list_offer_currencies() -> list[str]:
    base_currencies = ["EUR", "USD", "TRY"]
    with get_session() as session:
        query = (
            select(Offer.currency)
            .where(Offer.currency.is_not(None), Offer.currency != "")
            .distinct()
            .order_by(Offer.currency.asc())
        )
        dynamic = [value for value in session.scalars(query) if value]

    return base_currencies + [value for value in dynamic if value not in base_currencies]


def get_offer_summary() -> dict[str, int]:
    with get_session() as session:
        waiting = (
            session.scalar(
                select(func.count())
                .select_from(Offer)
                .where(Offer.status.in_(PENDING_OFFER_STATUSES))
            )
            or 0
        )
        accepted = (
            session.scalar(
                select(func.count()).select_from(Offer).where(Offer.status == "Kabul Edildi")
            )
            or 0
        )

    return {
        "waiting_offers": waiting,
        "accepted_offers": accepted,
    }


def get_offer_status_counts(statuses: list[str]) -> list[tuple[str, int]]:
    with get_session() as session:
        query = (
            select(Offer.status, func.count())
            .where(Offer.status.in_(statuses))
            .group_by(Offer.status)
        )
        counts = {status: count for status, count in session.execute(query).all()}

    return [(status, counts.get(status, 0)) for status in statuses]
