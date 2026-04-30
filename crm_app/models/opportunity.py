from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from crm_app.database.base import Base


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    stage: Mapped[str] = mapped_column(String(120), default="Yeni Lead")
    expected_amount: Mapped[float] = mapped_column(Float, default=0)
    currency: Mapped[str] = mapped_column(String(16), default="EUR")
    probability: Mapped[int] = mapped_column(Integer, default=0)
    expected_close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    company = relationship("Company", back_populates="opportunities")
    contact = relationship("Contact", back_populates="opportunities")
