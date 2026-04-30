from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from crm_app.database.session import get_session
from crm_app.models import Action, Company, Contact


def list_actions(
    search_text: str = "",
    record_type: str = "",
    action_type: str = "",
    channel: str = "",
) -> list[Action]:
    with get_session() as session:
        query = (
            select(Action)
            .join(Action.company, isouter=True)
            .join(Action.contact, isouter=True)
            .options(joinedload(Action.company), joinedload(Action.contact))
            .order_by(Action.created_at.desc())
        )

        if search_text:
            term = f"%{search_text.lower()}%"
            query = query.where(
                func.lower(func.coalesce(Action.note, "")).like(term)
                | func.lower(func.coalesce(Action.result, "")).like(term)
                | func.lower(func.coalesce(Action.next_action, "")).like(term)
                | func.lower(func.coalesce(Action.action_type, "")).like(term)
                | func.lower(func.coalesce(Action.channel, "")).like(term)
                | func.lower(func.coalesce(Company.name, "")).like(term)
                | func.lower(func.coalesce(Contact.name, "")).like(term)
            )

        if record_type == "Sirket":
            query = query.where(Action.contact_id.is_(None))
        elif record_type == "Kisi":
            query = query.where(Action.contact_id.is_not(None))

        if action_type:
            query = query.where(Action.action_type == action_type)

        if channel:
            query = query.where(Action.channel == channel)

        return list(session.scalars(query).unique())


def get_action(action_id: int) -> Action | None:
    with get_session() as session:
        query = (
            select(Action)
            .options(joinedload(Action.company), joinedload(Action.contact))
            .where(Action.id == action_id)
        )
        return session.scalars(query).first()


def create_action(data: dict[str, Any]) -> Action:
    with get_session() as session:
        action = Action(**data)
        session.add(action)
        session.commit()
        session.refresh(action)
        return action


def update_action(action_id: int, data: dict[str, Any]) -> None:
    with get_session() as session:
        action = session.get(Action, action_id)
        if not action:
            return

        for field, value in data.items():
            setattr(action, field, value)

        session.commit()


def delete_action(action_id: int) -> None:
    with get_session() as session:
        action = session.get(Action, action_id)
        if not action:
            return

        session.delete(action)
        session.commit()


def list_action_types() -> list[str]:
    with get_session() as session:
        query = (
            select(Action.action_type)
            .where(Action.action_type.is_not(None), Action.action_type != "")
            .distinct()
            .order_by(Action.action_type.asc())
        )
        return [value for value in session.scalars(query) if value]


def list_channels() -> list[str]:
    with get_session() as session:
        query = (
            select(Action.channel)
            .where(Action.channel.is_not(None), Action.channel != "")
            .distinct()
            .order_by(Action.channel.asc())
        )
        return [value for value in session.scalars(query) if value]
