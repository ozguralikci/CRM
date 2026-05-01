from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from crm_app.database.base import Base


class ResearchTarget(Base):
    __tablename__ = "research_targets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    website: Mapped[str] = mapped_column(String(512), default="")
    linkedin_company_url: Mapped[str] = mapped_column(String(512), default="")
    country: Mapped[str] = mapped_column(String(120), default="")
    city: Mapped[str] = mapped_column(String(120), default="")
    sector: Mapped[str] = mapped_column(String(255), default="")
    company_type: Mapped[str] = mapped_column(String(120), default="")
    production_structure: Mapped[str] = mapped_column(String(255), default="")
    product_fit_signals: Mapped[str] = mapped_column(Text, default="")
    fit_score: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(64), default="new")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
