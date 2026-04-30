from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from crm_app.database.base import Base


class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"), nullable=True)
    offer_no: Mapped[str] = mapped_column(String(120), nullable=False)
    date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[float] = mapped_column(Float, default=0)
    currency: Mapped[str] = mapped_column(String(16), default="EUR")
    status: Mapped[str] = mapped_column(String(120), default="")
    file_path: Mapped[str] = mapped_column(String(500), default="")
    note: Mapped[str] = mapped_column(Text, default="")

    company = relationship("Company", back_populates="offers")
    contact = relationship("Contact", back_populates="offers")
