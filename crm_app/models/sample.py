from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from crm_app.database.base import Base


class Sample(Base):
    __tablename__ = "samples"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), nullable=False)
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"), nullable=True)
    product: Mapped[str] = mapped_column(String(255), default="")
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    sent_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(120), default="")
    note: Mapped[str] = mapped_column(Text, default="")

    company = relationship("Company", back_populates="samples")
    contact = relationship("Contact", back_populates="samples")
