from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select

from crm_app.database.session import get_session
from crm_app.models import Action, Company, Contact, FieldDefinition


def seed_sample_data() -> None:
    with get_session() as session:
        existing_company = session.scalar(select(Company.id).limit(1))
        if existing_company:
            return

        company_1 = Company(
            name="Anadolu Makine",
            country="Turkiye",
            city="Istanbul",
            website="https://anadolumakine.com",
            linkedin="https://linkedin.com/company/anadolu-makine",
            priority=5,
        )
        company_2 = Company(
            name="Ege Plastik",
            country="Turkiye",
            city="Izmir",
            website="https://egeplastik.com",
            linkedin="https://linkedin.com/company/ege-plastik",
            priority=4,
        )
        company_3 = Company(
            name="Balkan Trade",
            country="Bulgaristan",
            city="Sofya",
            website="https://balkantrade.eu",
            linkedin="https://linkedin.com/company/balkan-trade",
            priority=2,
        )

        session.add_all([company_1, company_2, company_3])
        session.flush()

        contact_1 = Contact(
            company_id=company_1.id,
            name="Merve Aydin",
            title="Satinalma Muduru",
            email="merve@anadolumakine.com",
            phone="+90 532 000 0001",
        )
        contact_2 = Contact(
            company_id=company_2.id,
            name="Can Demir",
            title="Operasyon Sorumlusu",
            email="can@egeplastik.com",
            phone="+90 532 000 0002",
        )

        action_1 = Action(
            company_id=company_1.id,
            contact=contact_1,
            action_type="Arama",
            channel="Telefon",
            note="Ilk tanisma gorusmesi yapildi.",
            result="Olumlu",
            next_action="Teklif gonder",
            next_action_date=date.today() + timedelta(days=1),
        )
        action_2 = Action(
            company_id=company_2.id,
            contact=contact_2,
            action_type="E-posta",
            channel="E-posta",
            note="Numune talebi bekleniyor.",
            result="Beklemede",
            next_action="Takip aramasi",
            next_action_date=date.today() - timedelta(days=2),
        )

        field_definition = FieldDefinition(
            entity_type="company",
            field_key="sektor",
            label="Sektor",
            field_type="text",
            is_required=False,
            is_visible=True,
            sort_order=1,
        )

        session.add_all([contact_1, contact_2, action_1, action_2, field_definition])
        session.commit()
