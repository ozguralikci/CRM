from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload, selectinload

from crm_app.database.session import get_session
from crm_app.models import Action, Company, Contact
from crm_app.services.field_service import delete_entity_field_values, save_field_values


def list_contacts(search_text: str = "") -> list[Contact]:
    with get_session() as session:
        query = (
            select(Contact)
            .options(joinedload(Contact.company))
            .order_by(Contact.created_at.desc())
        )

        if search_text:
            term = f"%{search_text.lower()}%"
            query = query.where(func.lower(Contact.name).like(term))

        return list(session.scalars(query).unique())


def get_contact(contact_id: int) -> Contact | None:
    with get_session() as session:
        query = (
            select(Contact)
            .options(
                joinedload(Contact.company),
                selectinload(Contact.actions).selectinload(Action.company),
            )
            .where(Contact.id == contact_id)
        )
        return session.scalars(query).first()


def create_contact(data: dict[str, Any]) -> Contact:
    payload = dict(data)
    custom_values = payload.pop("custom_values", {})
    with get_session() as session:
        contact = Contact(**payload)
        session.add(contact)
        session.commit()
        session.refresh(contact)
        save_field_values("contact", contact.id, custom_values)
        return contact


def update_contact(contact_id: int, data: dict[str, Any]) -> None:
    payload = dict(data)
    custom_values = payload.pop("custom_values", {})
    with get_session() as session:
        contact = session.get(Contact, contact_id)
        if not contact:
            return

        for field, value in payload.items():
            setattr(contact, field, value)

        session.commit()
        save_field_values("contact", contact_id, custom_values)


def delete_contact(contact_id: int) -> None:
    with get_session() as session:
        contact = session.get(Contact, contact_id)
        if not contact:
            return

        session.delete(contact)
        session.commit()
    delete_entity_field_values("contact", contact_id)


def list_company_choices() -> list[Company]:
    with get_session() as session:
        query = select(Company).order_by(Company.name.asc())
        return list(session.scalars(query))


def list_contact_choices(company_id: int | None = None) -> list[Contact]:
    with get_session() as session:
        query = select(Contact).options(joinedload(Contact.company)).order_by(Contact.name.asc())
        if company_id:
            query = query.where(Contact.company_id == company_id)
        return list(session.scalars(query).unique())
