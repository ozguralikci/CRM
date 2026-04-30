from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from crm_app.database.base import Base


class FieldDefinition(Base):
    __tablename__ = "field_definitions"
    __table_args__ = (UniqueConstraint("entity_type", "field_name", name="uq_field_entity_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    field_key: Mapped[str] = mapped_column("field_name", String(100), nullable=False)
    label: Mapped[str] = mapped_column("field_label", String(120), nullable=False)
    field_type: Mapped[str] = mapped_column(String(50), default="text")
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    options_json: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    values = relationship("FieldValue", back_populates="definition", cascade="all, delete-orphan")


class FieldValue(Base):
    __tablename__ = "field_values"

    id: Mapped[int] = mapped_column(primary_key=True)
    field_definition_id: Mapped[int] = mapped_column(ForeignKey("field_definitions.id"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[int] = mapped_column(nullable=False)
    value_text: Mapped[str] = mapped_column(Text, default="")

    definition = relationship("FieldDefinition", back_populates="values")
