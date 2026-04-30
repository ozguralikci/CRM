from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from crm_app.database.base import Base


class Action(Base):
    __tablename__ = "actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"), nullable=True)
    action_type: Mapped[str] = mapped_column(String(120), default="")
    channel: Mapped[str] = mapped_column(String(120), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[str] = mapped_column(String(255), default="")
    next_action: Mapped[str] = mapped_column(String(255), default="")
    next_action_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="actions")
    contact = relationship("Contact", back_populates="actions")
