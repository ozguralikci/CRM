from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from crm_app.database.session import get_session
from crm_app.services.field_service import delete_entity_field_values, save_field_values
from crm_app.models import Action, Company, Offer, Opportunity, Sample


def list_companies(search_text: str = "", priority: int | None = None) -> list[Company]:
    with get_session() as session:
        query = (
            select(Company)
            .options(
                selectinload(Company.contacts),
                selectinload(Company.actions),
            )
            .order_by(Company.created_at.desc())
        )

        if search_text:
            term = f"%{search_text.lower()}%"
            query = query.where(
                func.lower(Company.name).like(term)
                | func.lower(Company.city).like(term)
                | func.lower(Company.country).like(term)
            )

        if priority:
            query = query.where(Company.priority == priority)

        return list(session.scalars(query).unique())


def create_company(data: dict[str, Any]) -> Company:
    payload = dict(data)
    custom_values = payload.pop("custom_values", {})
    with get_session() as session:
        company = Company(**payload)
        session.add(company)
        session.commit()
        session.refresh(company)
        save_field_values("company", company.id, custom_values)
        return company


def update_company(company_id: int, data: dict[str, Any]) -> None:
    payload = dict(data)
    custom_values = payload.pop("custom_values", {})
    with get_session() as session:
        company = session.get(Company, company_id)
        if not company:
            return

        for field, value in payload.items():
            setattr(company, field, value)

        session.commit()
        save_field_values("company", company_id, custom_values)


def delete_company(company_id: int) -> None:
    with get_session() as session:
        company = session.get(Company, company_id)
        if not company:
            return

        session.delete(company)
        session.commit()
    delete_entity_field_values("company", company_id)


def get_company(company_id: int) -> Company | None:
    with get_session() as session:
        query = (
            select(Company)
            .options(
                selectinload(Company.contacts),
                selectinload(Company.actions).selectinload(Action.contact),
                selectinload(Company.opportunities).selectinload(Opportunity.contact),
                selectinload(Company.offers).selectinload(Offer.contact),
                selectinload(Company.samples).selectinload(Sample.contact),
            )
            .where(Company.id == company_id)
        )
        return session.scalars(query).first()
