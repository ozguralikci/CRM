from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select

from crm_app.database.session import get_session
from crm_app.models import FieldDefinition, FieldValue

logger = logging.getLogger(__name__)

FIELD_TYPES = ["text", "textarea", "number", "date", "boolean", "select"]
ENTITY_LABELS = {"company": "Şirket", "contact": "Kişi"}
CORE_FIELD_KEYS = {
    "company": {"name"},
    "contact": {"name", "company_id"},
}
COMPANY_COMMERCIAL_FIELDS = [
    {"field_key": "kullandigi_urun", "label": "Kullandığı Ürün", "field_type": "text"},
    {"field_key": "potansiyel_urun", "label": "Potansiyel Ürün", "field_type": "text"},
    {"field_key": "kullanim_alani", "label": "Kullanım Alanı", "field_type": "textarea"},
    {"field_key": "tahmini_tuketim", "label": "Tahmini Tüketim", "field_type": "text"},
]
COMPANY_AI_FIELDS = [
    {"field_key": "ai_analizi", "label": "Yapay Zekâ Analizi", "field_type": "textarea", "is_visible": False},
    {"field_key": "satis_stratejisi", "label": "Satış Stratejisi", "field_type": "textarea", "is_visible": False},
    {
        "field_key": "onerilen_sonraki_adim",
        "label": "Önerilen Sonraki Adım",
        "field_type": "textarea",
        "is_visible": False,
    },
    {"field_key": "ai_uygunluk_skoru", "label": "AI Uygunluk Skoru", "field_type": "number", "is_visible": False},
    {"field_key": "ai_son_analiz_tarihi", "label": "Son Analiz Tarihi", "field_type": "text", "is_visible": False},
]
COMPANY_PROSPECTING_FIELDS = [
    {"field_key": "sektor", "label": "Sektör", "field_type": "text"},
    {"field_key": "calisan_sayisi", "label": "Çalışan Sayısı", "field_type": "text"},
    {
        "field_key": "kaynak",
        "label": "Kaynak",
        "field_type": "select",
        "options_text": "LinkedIn, Referans, Web Sitesi, Fuar, E-posta, Sales Navigator",
    },
    {"field_key": "referans_noktasi", "label": "Referans Noktası", "field_type": "textarea"},
    {
        "field_key": "durum",
        "label": "Durum",
        "field_type": "select",
        "options_text": "Yeni Hedef, Araştırılıyor, İlk Temas, Takipte, Teklif Aşamasında, Pasif",
    },
]
COMPANY_BUSINESS_FIELDS = COMPANY_PROSPECTING_FIELDS + COMPANY_COMMERCIAL_FIELDS + COMPANY_AI_FIELDS
CONTACT_INTELLIGENCE_FIELDS = [
    {
        "field_key": "kisi_genel_degerlendirme",
        "label": "Genel Değerlendirme",
        "field_type": "textarea",
        "is_visible": False,
    },
    {
        "field_key": "kisi_davranis_analizi",
        "label": "Davranış Analizi",
        "field_type": "textarea",
        "is_visible": False,
    },
    {
        "field_key": "kisi_ticari_yaklasim",
        "label": "Ticari Yaklaşım",
        "field_type": "textarea",
        "is_visible": False,
    },
    {
        "field_key": "kisi_risk_notlari",
        "label": "Risk Notları",
        "field_type": "textarea",
        "is_visible": False,
    },
    {
        "field_key": "kisi_serbest_not",
        "label": "Serbest Not",
        "field_type": "textarea",
        "is_visible": False,
    },
    {
        "field_key": "kisi_etiketleri",
        "label": "İstihbarat Etiketleri",
        "field_type": "text",
        "is_visible": False,
    },
    {
        "field_key": "kisi_istihbarat_guncelleme_tarihi",
        "label": "İstihbarat Güncelleme Tarihi",
        "field_type": "text",
        "is_visible": False,
    },
]


def normalize_field_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", normalized.lower()).strip("_")
    return normalized or "custom_field"


def parse_options(options_json: str) -> list[str]:
    if not options_json:
        return []

    try:
        data = json.loads(options_json)
        if isinstance(data, list):
            return [str(item).strip() for item in data if str(item).strip()]
    except json.JSONDecodeError:
        pass

    return [item.strip() for item in options_json.split(",") if item.strip()]


def encode_options(raw_options: str) -> str:
    values = [item.strip() for item in raw_options.split(",") if item.strip()]
    return json.dumps(values, ensure_ascii=True)


def list_field_definitions(
    entity_type: str,
    search_text: str = "",
    include_hidden: bool = True,
) -> list[FieldDefinition]:
    with get_session() as session:
        query = (
            select(FieldDefinition)
            .where(FieldDefinition.entity_type == entity_type)
            .order_by(FieldDefinition.sort_order.asc(), FieldDefinition.id.asc())
        )

        if search_text:
            term = f"%{search_text.lower()}%"
            query = query.where(
                func.lower(FieldDefinition.label).like(term)
                | func.lower(FieldDefinition.field_key).like(term)
            )

        if not include_hidden:
            query = query.where(FieldDefinition.is_visible.is_(True))

        return list(session.scalars(query))


def get_field_definition(field_definition_id: int) -> FieldDefinition | None:
    with get_session() as session:
        return session.get(FieldDefinition, field_definition_id)


def list_visible_field_definitions(entity_type: str) -> list[FieldDefinition]:
    return list_field_definitions(entity_type, include_hidden=False)


def ensure_company_business_fields() -> list[FieldDefinition]:
    with get_session() as session:
        existing = list(
            session.scalars(
                select(FieldDefinition)
                .where(FieldDefinition.entity_type == "company")
                .order_by(FieldDefinition.sort_order.asc(), FieldDefinition.id.asc())
            )
        )
        existing_map = {definition.field_key: definition for definition in existing}
        next_order = max((definition.sort_order for definition in existing), default=0) + 1

        for config in COMPANY_BUSINESS_FIELDS:
            if config["field_key"] in existing_map:
                continue
            definition = FieldDefinition(
                entity_type="company",
                field_key=config["field_key"],
                label=config["label"],
                field_type=config["field_type"],
                is_required=False,
                is_visible=bool(config.get("is_visible", True)),
                sort_order=next_order,
                options_json=encode_options(config.get("options_text", ""))
                if config.get("field_type") == "select"
                else "",
            )
            next_order += 1
            session.add(definition)
            existing.append(definition)
            existing_map[config["field_key"]] = definition

        session.commit()
        return [
            existing_map[config["field_key"]]
            for config in COMPANY_BUSINESS_FIELDS
            if config["field_key"] in existing_map
        ]


def ensure_company_commercial_fields() -> list[FieldDefinition]:
    definitions = ensure_company_business_fields()
    commercial_keys = {config["field_key"] for config in COMPANY_COMMERCIAL_FIELDS}
    return [definition for definition in definitions if definition.field_key in commercial_keys]


def ensure_company_ai_fields() -> list[FieldDefinition]:
    definitions = ensure_company_business_fields()
    ai_keys = {config["field_key"] for config in COMPANY_AI_FIELDS}
    return [definition for definition in definitions if definition.field_key in ai_keys]


def ensure_contact_intelligence_fields() -> list[FieldDefinition]:
    with get_session() as session:
        existing = list(
            session.scalars(
                select(FieldDefinition)
                .where(FieldDefinition.entity_type == "contact")
                .order_by(FieldDefinition.sort_order.asc(), FieldDefinition.id.asc())
            )
        )
        existing_map = {definition.field_key: definition for definition in existing}
        next_order = max((definition.sort_order for definition in existing), default=0) + 1

        for config in CONTACT_INTELLIGENCE_FIELDS:
            if config["field_key"] in existing_map:
                continue
            definition = FieldDefinition(
                entity_type="contact",
                field_key=config["field_key"],
                label=config["label"],
                field_type=config["field_type"],
                is_required=False,
                is_visible=bool(config.get("is_visible", True)),
                sort_order=next_order,
                options_json=encode_options(config.get("options_text", ""))
                if config.get("field_type") == "select"
                else "",
            )
            next_order += 1
            session.add(definition)
            existing.append(definition)
            existing_map[config["field_key"]] = definition

        session.commit()
        return [
            existing_map[config["field_key"]]
            for config in CONTACT_INTELLIGENCE_FIELDS
            if config["field_key"] in existing_map
        ]


def create_field_definition(data: dict[str, Any]) -> FieldDefinition:
    payload = _prepare_definition_payload(data)

    with get_session() as session:
        _ensure_unique_key(session, payload["entity_type"], payload["field_key"])
        if payload["sort_order"] <= 0:
            max_order = (
                session.scalar(
                    select(func.max(FieldDefinition.sort_order)).where(
                        FieldDefinition.entity_type == payload["entity_type"]
                    )
                )
                or 0
            )
            payload["sort_order"] = max_order + 1

        definition = FieldDefinition(**payload)
        session.add(definition)
        session.commit()
        session.refresh(definition)
        return definition


def update_field_definition(field_definition_id: int, data: dict[str, Any]) -> None:
    payload = _prepare_definition_payload(data)

    with get_session() as session:
        definition = session.get(FieldDefinition, field_definition_id)
        if not definition:
            return

        _ensure_unique_key(
            session,
            payload["entity_type"],
            payload["field_key"],
            exclude_id=field_definition_id,
        )

        for field, value in payload.items():
            setattr(definition, field, value)

        session.commit()


def delete_field_definition(field_definition_id: int) -> None:
    with get_session() as session:
        definition = session.get(FieldDefinition, field_definition_id)
        if not definition:
            return

        session.delete(definition)
        session.commit()


def move_field_definition(field_definition_id: int, direction: str) -> None:
    with get_session() as session:
        definition = session.get(FieldDefinition, field_definition_id)
        if not definition:
            return

        query = (
            select(FieldDefinition)
            .where(FieldDefinition.entity_type == definition.entity_type)
            .order_by(FieldDefinition.sort_order.asc(), FieldDefinition.id.asc())
        )
        definitions = list(session.scalars(query))
        index = next((i for i, item in enumerate(definitions) if item.id == field_definition_id), None)
        if index is None:
            return

        swap_index = index - 1 if direction == "up" else index + 1
        if swap_index < 0 or swap_index >= len(definitions):
            return

        current = definitions[index]
        target = definitions[swap_index]
        current.sort_order, target.sort_order = target.sort_order, current.sort_order
        session.commit()


def get_field_values(entity_type: str, entity_id: int) -> dict[str, str]:
    if not entity_id:
        return {}

    with get_session() as session:
        query = (
            select(FieldValue, FieldDefinition)
            .join(FieldDefinition, FieldValue.field_definition_id == FieldDefinition.id)
            .where(FieldValue.entity_type == entity_type, FieldValue.entity_id == entity_id)
        )
        rows = session.execute(query).all()

    return {definition.field_key: value.value_text for value, definition in rows}


def get_field_values_map(entity_type: str, entity_ids: list[int]) -> dict[int, dict[str, str]]:
    if not entity_ids:
        return {}

    with get_session() as session:
        query = (
            select(FieldValue, FieldDefinition)
            .join(FieldDefinition, FieldValue.field_definition_id == FieldDefinition.id)
            .where(FieldValue.entity_type == entity_type, FieldValue.entity_id.in_(entity_ids))
        )
        rows = session.execute(query).all()

    values_map: dict[int, dict[str, str]] = {entity_id: {} for entity_id in entity_ids}
    for value, definition in rows:
        values_map.setdefault(value.entity_id, {})[definition.field_key] = value.value_text
    return values_map


def save_field_values(entity_type: str, entity_id: int, values: dict[str, Any]) -> None:
    if not entity_id:
        return

    payload = dict(values or {})
    with get_session() as session:
        definitions = list(
            session.scalars(
                select(FieldDefinition).where(FieldDefinition.entity_type == entity_type)
            )
        )
        baseline_query = (
            select(FieldValue, FieldDefinition)
            .join(FieldDefinition, FieldValue.field_definition_id == FieldDefinition.id)
            .where(FieldValue.entity_type == entity_type, FieldValue.entity_id == entity_id)
        )
        baseline_rows = session.execute(baseline_query).all()
        merged: dict[str, Any] = {
            definition.field_key: fv.value_text for fv, definition in baseline_rows
        }
        merged.update(payload)

        payload_keys = sorted(payload.keys())
        logger.info(
            "save_field_values start | entity_type=%s | entity_id=%s | payload_keys=%s | "
            "baseline_field_count=%s",
            entity_type,
            entity_id,
            payload_keys,
            len(baseline_rows),
        )

        existing_map = {
            value.field_definition_id: value
            for value in session.scalars(
                select(FieldValue).where(
                    FieldValue.entity_type == entity_type,
                    FieldValue.entity_id == entity_id,
                )
            )
        }

        for definition in definitions:
            raw_value = merged.get(definition.field_key)
            serialized = serialize_field_value(definition.field_type, raw_value)
            existing = existing_map.get(definition.id)

            if serialized == "":
                if existing:
                    session.delete(existing)
                continue

            if existing:
                existing.value_text = serialized
            else:
                session.add(
                    FieldValue(
                        field_definition_id=definition.id,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        value_text=serialized,
                    )
                )

        session.commit()
        logger.info(
            "save_field_values committed | entity_type=%s | entity_id=%s",
            entity_type,
            entity_id,
        )


def delete_entity_field_values(entity_type: str, entity_id: int) -> None:
    if not entity_id:
        return

    with get_session() as session:
        values = list(
            session.scalars(
                select(FieldValue).where(
                    FieldValue.entity_type == entity_type,
                    FieldValue.entity_id == entity_id,
                )
            )
        )
        for value in values:
            session.delete(value)
        session.commit()


def serialize_field_value(field_type: str, value: Any) -> str:
    if field_type == "boolean":
        return "1" if bool(value) else ""

    if value is None:
        return ""

    if field_type == "number":
        if value == "":
            return ""
        return str(value)

    if field_type == "date":
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        return str(value).strip()

    text = str(value).strip()
    return text


def deserialize_field_value(field_type: str, value_text: str) -> Any:
    if value_text in (None, ""):
        return None

    if field_type == "boolean":
        return value_text == "1"

    if field_type == "number":
        try:
            return float(value_text)
        except ValueError:
            return None

    if field_type == "date":
        try:
            return date.fromisoformat(value_text)
        except ValueError:
            return None

    return value_text


def get_visible_display_rows(entity_type: str, entity_id: int) -> list[tuple[str, str]]:
    definitions = list_visible_field_definitions(entity_type)
    values = get_field_values(entity_type, entity_id)
    rows: list[tuple[str, str]] = []

    for definition in definitions:
        raw_value = values.get(definition.field_key, "")
        if raw_value in ("", None):
            continue

        display_value = raw_value
        if definition.field_type == "boolean":
            display_value = "Evet" if raw_value == "1" else "Hayır"
        rows.append((definition.label, display_value))

    return rows


def _prepare_definition_payload(data: dict[str, Any]) -> dict[str, Any]:
    field_key = normalize_field_key(data.get("field_key") or data.get("label", ""))
    if field_key in CORE_FIELD_KEYS.get(data["entity_type"], set()):
        raise ValueError("Çekirdek alan anahtarları özel alan olarak kullanılamaz.")
    options_json = encode_options(data.get("options_text", "")) if data.get("field_type") == "select" else ""

    return {
        "entity_type": data["entity_type"],
        "field_key": field_key,
        "label": data["label"].strip(),
        "field_type": data["field_type"],
        "is_required": bool(data.get("is_required")),
        "is_visible": bool(data.get("is_visible", True)),
        "sort_order": int(data.get("sort_order") or 0),
        "options_json": options_json,
    }


def _ensure_unique_key(
    session: Any,
    entity_type: str,
    field_key: str,
    exclude_id: int | None = None,
) -> None:
    query = select(FieldDefinition).where(
        FieldDefinition.entity_type == entity_type,
        FieldDefinition.field_key == field_key,
    )
    if exclude_id:
        query = query.where(FieldDefinition.id != exclude_id)

    existing = session.scalars(query).first()
    if existing:
        raise ValueError("Bu teknik anahtar zaten kullanılıyor.")
