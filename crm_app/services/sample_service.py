from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from crm_app.database.session import get_session
from crm_app.models import Company, Contact, Sample

TEST_IN_PROGRESS_STATUSES = ["Gonderildi", "Ulasti", "Testte", "Geri Donus Bekleniyor"]
SAMPLE_SUMMARY_STATUSES = ["Hazirlaniyor", "Gonderildi", "Testte", "Olumlu", "Olumsuz"]


def list_samples(
    search_text: str = "",
    status: str = "",
    company_id: int | None = None,
) -> list[Sample]:
    with get_session() as session:
        query = (
            select(Sample)
            .join(Sample.company)
            .join(Sample.contact, isouter=True)
            .options(joinedload(Sample.company), joinedload(Sample.contact))
            .order_by(Sample.sent_date.is_(None), Sample.sent_date.desc(), Sample.id.desc())
        )

        if search_text:
            term = f"%{search_text.lower()}%"
            query = query.where(
                func.lower(func.coalesce(Sample.product, "")).like(term)
                | func.lower(func.coalesce(Sample.note, "")).like(term)
                | func.lower(func.coalesce(Company.name, "")).like(term)
                | func.lower(func.coalesce(Contact.name, "")).like(term)
            )

        if status:
            query = query.where(Sample.status == status)

        if company_id:
            query = query.where(Sample.company_id == company_id)

        return list(session.scalars(query).unique())


def get_sample(sample_id: int) -> Sample | None:
    with get_session() as session:
        query = (
            select(Sample)
            .options(joinedload(Sample.company), joinedload(Sample.contact))
            .where(Sample.id == sample_id)
        )
        return session.scalars(query).first()


def create_sample(data: dict[str, Any]) -> Sample:
    with get_session() as session:
        sample = Sample(**data)
        session.add(sample)
        session.commit()
        session.refresh(sample)
        return sample


def update_sample(sample_id: int, data: dict[str, Any]) -> None:
    with get_session() as session:
        sample = session.get(Sample, sample_id)
        if not sample:
            return

        for field, value in data.items():
            setattr(sample, field, value)

        session.commit()


def delete_sample(sample_id: int) -> None:
    with get_session() as session:
        sample = session.get(Sample, sample_id)
        if not sample:
            return

        session.delete(sample)
        session.commit()


def list_sample_statuses() -> list[str]:
    base_statuses = [
        "Hazirlaniyor",
        "Gonderildi",
        "Ulasti",
        "Testte",
        "Geri Donus Bekleniyor",
        "Olumlu",
        "Olumsuz",
    ]
    with get_session() as session:
        query = (
            select(Sample.status)
            .where(Sample.status.is_not(None), Sample.status != "")
            .distinct()
            .order_by(Sample.status.asc())
        )
        dynamic = [value for value in session.scalars(query) if value]

    return base_statuses + [value for value in dynamic if value not in base_statuses]


def get_sample_summary() -> dict[str, int]:
    with get_session() as session:
        waiting_samples = (
            session.scalar(
                select(func.count())
                .select_from(Sample)
                .where(Sample.status.in_(["Hazirlaniyor", "Gonderildi", "Testte", "Geri Donus Bekleniyor"]))
            )
            or 0
        )
        testing_samples = (
            session.scalar(
                select(func.count()).select_from(Sample).where(Sample.status.in_(TEST_IN_PROGRESS_STATUSES))
            )
            or 0
        )
        positive_samples = (
            session.scalar(
                select(func.count()).select_from(Sample).where(Sample.status == "Olumlu")
            )
            or 0
        )

    return {
        "waiting_samples": waiting_samples,
        "testing_samples": testing_samples,
        "positive_samples": positive_samples,
    }


def get_sample_status_counts(statuses: list[str] | None = None) -> list[tuple[str, int]]:
    target_statuses = statuses or SAMPLE_SUMMARY_STATUSES
    with get_session() as session:
        query = (
            select(Sample.status, func.count())
            .where(Sample.status.in_(target_statuses))
            .group_by(Sample.status)
        )
        counts = {status: count for status, count in session.execute(query).all()}

    return [(status, counts.get(status, 0)) for status in target_statuses]
