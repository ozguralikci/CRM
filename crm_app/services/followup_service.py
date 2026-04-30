from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select

from crm_app.database.session import get_session
from crm_app.models import Action, Company, Offer, Opportunity, Sample
from crm_app.services.company_service import get_company
from crm_app.services.field_service import get_field_values
from crm_app.services.offer_service import PENDING_OFFER_STATUSES
from crm_app.services.opportunity_service import ACTIVE_CLOSED_STAGES

ACTIVE_SAMPLE_ALERT_STATUSES = {
    "Gonderildi",
    "Ulasti",
    "Testte",
    "Geri Donus Bekleniyor",
    "Olumlu",
    "Olumsuz",
}
AI_TEXT_KEYS = ("ai_analizi", "satis_stratejisi", "onerilen_sonraki_adim")
AI_SCORE_KEY = "ai_uygunluk_skoru"
QUOTE_FOLLOWUP_STALE_DAYS = 7
SAMPLE_FOLLOWUP_STALE_DAYS = 5
NEXT_ACTION_MISSING_DAYS = 5


@dataclass(slots=True)
class FollowUpAlert:
    rule_key: str
    rule_label: str
    priority: int
    age_days: int
    company_id: int
    company_name: str
    company_priority: int
    title: str
    description: str
    primary_action_key: str
    primary_action_label: str
    secondary_action_key: str = ""
    secondary_action_label: str = ""
    contact_id: int | None = None
    opportunity_id: int | None = None
    offer_id: int | None = None
    sample_id: int | None = None
    action_id: int | None = None
    suggested_action_type: str = "Takip"
    suggested_channel: str = "Telefon"
    suggested_note: str = ""
    suggested_next_action: str = ""
    suggested_next_action_date: date | None = None
    suggested_opportunity_title: str = ""
    suggested_opportunity_stage: str = "Takipte"
    suggested_opportunity_note: str = ""


def list_smart_followup_alerts(limit: int = 8) -> list[FollowUpAlert]:
    today = date.today()
    max_candidates = max(limit * 2, 12)
    with get_session() as session:
        overdue_ids = list(
            session.scalars(
                select(Action.company_id)
                .where(
                    Action.company_id.is_not(None),
                    Action.next_action_date.is_not(None),
                    Action.next_action_date < today,
                )
                .order_by(Action.next_action_date.asc())
                .limit(max_candidates)
            )
        )
        stale_quote_ids = list(
            session.scalars(
                select(Opportunity.company_id)
                .where(Opportunity.stage == "Teklif Verildi")
                .order_by(Opportunity.updated_at.asc())
                .limit(max_candidates)
            )
        )
        sample_ids = list(
            session.scalars(
                select(Sample.company_id)
                .where(
                    Sample.company_id.is_not(None),
                    Sample.status.in_(tuple(ACTIVE_SAMPLE_ALERT_STATUSES)),
                    Sample.sent_date.is_not(None),
                )
                .order_by(Sample.sent_date.asc())
                .limit(max_candidates)
            )
        )
        active_opportunity_ids = list(
            session.scalars(
                select(Opportunity.company_id)
                .where(
                    Opportunity.company_id.is_not(None),
                    ~Opportunity.stage.in_(tuple(ACTIVE_CLOSED_STAGES)),
                )
                .order_by(Opportunity.updated_at.desc())
                .limit(max_candidates)
            )
        )
        waiting_offer_ids = list(
            session.scalars(
                select(Offer.company_id)
                .where(
                    Offer.company_id.is_not(None),
                    Offer.status.in_(tuple(PENDING_OFFER_STATUSES)),
                )
                .order_by(Offer.date.desc())
                .limit(max_candidates)
            )
        )
        priority_ids = list(
            session.scalars(
                select(Company.id)
                .where(Company.priority >= 4)
                .order_by(Company.priority.desc(), Company.created_at.desc())
                .limit(max_candidates)
            )
        )

    candidate_ids: list[int] = []
    for company_id in (
        overdue_ids
        + stale_quote_ids
        + sample_ids
        + active_opportunity_ids
        + waiting_offer_ids
        + priority_ids
    ):
        if company_id is None or company_id in candidate_ids:
            continue
        candidate_ids.append(int(company_id))
        if len(candidate_ids) >= max_candidates:
            break

    alerts: list[FollowUpAlert] = []
    for company_id in candidate_ids:
        company_alerts = get_company_followup_alerts(company_id, limit=1)
        if company_alerts:
            alerts.append(company_alerts[0])
        if len(alerts) >= max_candidates:
            break

    alerts.sort(
        key=lambda item: (
            item.priority,
            -item.age_days,
            -item.company_priority,
            item.company_name.lower(),
        )
    )
    return alerts[:limit]


def get_company_followup_alerts(company_id: int, limit: int = 5) -> list[FollowUpAlert]:
    company = get_company(company_id)
    if not company:
        return []
    field_values = get_field_values("company", company_id)
    return _build_company_alerts(company, field_values)[:limit]


def _build_company_alerts(company: Company, field_values: dict[str, str]) -> list[FollowUpAlert]:
    alerts: list[FollowUpAlert] = []

    for builder in (
        _build_overdue_followup_alert,
        _build_stale_quote_alert,
        _build_positive_sample_without_opportunity_alert,
        _build_sample_followup_alert,
        _build_missing_contact_alert,
        _build_missing_next_action_alert,
        _build_missing_ai_alert,
    ):
        alert = builder(company, field_values)
        if alert:
            alerts.append(alert)

    alerts.sort(
        key=lambda item: (
            item.priority,
            -item.age_days,
            -item.company_priority,
            item.company_name.lower(),
        )
    )
    return alerts


def _build_overdue_followup_alert(
    company: Company,
    _field_values: dict[str, str],
) -> FollowUpAlert | None:
    today = date.today()
    overdue_actions = sorted(
        [
            action
            for action in company.actions
            if action.next_action_date
            and action.next_action_date < today
            and _action_still_requires_followup(company.actions, action)
        ],
        key=lambda item: item.next_action_date or today,
    )
    if not overdue_actions:
        return None

    action = overdue_actions[0]
    overdue_days = (today - action.next_action_date).days if action.next_action_date else 0
    subject = action.contact.name if action.contact else company.name
    next_action = action.next_action or action.action_type or "takip görüşmesi"
    return FollowUpAlert(
        rule_key="overdue_followup",
        rule_label="Gecikmiş Takip",
        priority=10,
        age_days=overdue_days,
        company_id=company.id,
        company_name=company.name,
        company_priority=company.priority,
        title="Takip tarihi geçmiş bir aksiyon var",
        description=(
            f"{subject} için planlanan '{next_action}' aksiyonu {overdue_days} gündür gecikmiş durumda. "
            "Takibi güncelleyip yeni temas adımını netleştirin."
        ),
        primary_action_key="create_action",
        primary_action_label="Aksiyon Oluştur",
        contact_id=action.contact_id,
        action_id=action.id,
        suggested_note=(
            f"Gecikmiş takip uyarısı: {subject} için '{next_action}' planı yeniden ele alınacak."
        ),
        suggested_next_action=next_action,
        suggested_next_action_date=today,
    )


def _build_stale_quote_alert(
    company: Company,
    _field_values: dict[str, str],
) -> FollowUpAlert | None:
    today = date.today()
    opportunities = sorted(
        [item for item in company.opportunities if (item.stage or "") == "Teklif Verildi"],
        key=lambda item: item.updated_at,
    )
    for opportunity in opportunities:
        reference_date = opportunity.updated_at.date()
        stale_days = (today - reference_date).days
        if stale_days < QUOTE_FOLLOWUP_STALE_DAYS:
            continue
        if _has_recent_action(company.actions, reference_date, opportunity.contact_id):
            continue
        return FollowUpAlert(
            rule_key="quote_followup_missing",
            rule_label="Teklif Sonrası Takip",
            priority=20,
            age_days=stale_days,
            company_id=company.id,
            company_name=company.name,
            company_priority=company.priority,
            title="Teklif sonrası geri dönüş alınmamış",
            description=(
                f"{opportunity.title} fırsatı 'Teklif Verildi' aşamasında. "
                f"Son {stale_days} gündür yeni bir takip aksiyonu görünmüyor."
            ),
            primary_action_key="create_action",
            primary_action_label="Aksiyon Oluştur",
            secondary_action_key="open_opportunity",
            secondary_action_label="Fırsatı Aç",
            contact_id=opportunity.contact_id,
            opportunity_id=opportunity.id,
            suggested_note=(
                f"{opportunity.title} fırsatı için teklif sonrası geri dönüş alınmadı. "
                "Müşteri geri bildirimi ve sonraki karar adımı teyit edilecek."
            ),
            suggested_next_action="Teklif geri dönüşünü al",
            suggested_next_action_date=today + timedelta(days=1),
        )
    return None


def _build_positive_sample_without_opportunity_alert(
    company: Company,
    _field_values: dict[str, str],
) -> FollowUpAlert | None:
    positive_samples = sorted(
        [
            sample
            for sample in company.samples
            if (sample.status or "") == "Olumlu" and sample.sent_date is not None
        ],
        key=lambda item: item.sent_date or date.min,
        reverse=True,
    )
    open_opportunity_exists = any(
        (opportunity.stage or "") not in ACTIVE_CLOSED_STAGES
        for opportunity in company.opportunities
    )
    if not positive_samples or open_opportunity_exists:
        return None

    sample = positive_samples[0]
    age_days = (date.today() - sample.sent_date).days if sample.sent_date else 0
    product_label = sample.product or "Numune"
    return FollowUpAlert(
        rule_key="positive_sample_without_opportunity",
        rule_label="Numune Sonrası Fırsat",
        priority=25,
        age_days=age_days,
        company_id=company.id,
        company_name=company.name,
        company_priority=company.priority,
        title="Olumlu numune sonrası fırsat açılmalı",
        description=(
            f"{product_label} için olumlu geri dönüş var ancak açık fırsat görünmüyor. "
            "Ticari süreci görünür kılmak için yeni fırsat açın."
        ),
        primary_action_key="create_opportunity",
        primary_action_label="Fırsat Aç",
        contact_id=sample.contact_id,
        sample_id=sample.id,
        suggested_opportunity_title=f"{product_label} sonrası ticari fırsat",
        suggested_opportunity_stage="Takipte",
        suggested_opportunity_note=(
            f"{product_label} numunesi olumlu değerlendirildi. Ticari fırsat ve sonraki satış planı açılıyor."
        ),
    )


def _build_sample_followup_alert(
    company: Company,
    _field_values: dict[str, str],
) -> FollowUpAlert | None:
    today = date.today()
    samples = sorted(
        [
            sample
            for sample in company.samples
            if (sample.status or "") in ACTIVE_SAMPLE_ALERT_STATUSES and sample.sent_date is not None
        ],
        key=lambda item: item.sent_date or date.min,
    )
    for sample in samples:
        if not sample.sent_date:
            continue
        age_days = (today - sample.sent_date).days
        if age_days < SAMPLE_FOLLOWUP_STALE_DAYS:
            continue
        if _has_recent_action(company.actions, sample.sent_date, sample.contact_id):
            continue
        product_label = sample.product or "Numune"
        return FollowUpAlert(
            rule_key="sample_followup_missing",
            rule_label="Numune Takibi",
            priority=30,
            age_days=age_days,
            company_id=company.id,
            company_name=company.name,
            company_priority=company.priority,
            title="Numune sonrası takip gerekiyor",
            description=(
                f"{product_label} için durum '{_display_value(sample.status)}'. "
                f"Gönderimden sonra {age_days} gündür kayıtlı bir ticari takip görünmüyor."
            ),
            primary_action_key="create_action",
            primary_action_label="Aksiyon Oluştur",
            contact_id=sample.contact_id,
            sample_id=sample.id,
            suggested_note=(
                f"{product_label} numunesi için geri bildirim alınması ve sonraki ticari adımın netleştirilmesi gerekiyor."
            ),
            suggested_next_action="Numune geri bildirimini al",
            suggested_next_action_date=today + timedelta(days=1),
        )
    return None


def _build_missing_contact_alert(
    company: Company,
    _field_values: dict[str, str],
) -> FollowUpAlert | None:
    has_context = bool(company.actions or company.offers or company.samples or company.opportunities)
    if company.contacts or not has_context:
        return None
    return FollowUpAlert(
        rule_key="missing_contact",
        rule_label="Kişi Kaydı Eksik",
        priority=35,
        age_days=0,
        company_id=company.id,
        company_name=company.name,
        company_priority=company.priority,
        title="Bu şirkette henüz kişi kaydı yok",
        description=(
            "Teklif, numune, fırsat veya aksiyon geçmişi var; ancak karar verici ya da ilgili kişi henüz eklenmemiş."
        ),
        primary_action_key="create_contact",
        primary_action_label="Kişi Ekle",
    )


def _build_missing_next_action_alert(
    company: Company,
    _field_values: dict[str, str],
) -> FollowUpAlert | None:
    today = date.today()
    active_opportunity = next(
        (
            opportunity
            for opportunity in sorted(company.opportunities, key=lambda item: item.updated_at, reverse=True)
            if (opportunity.stage or "") not in ACTIVE_CLOSED_STAGES
        ),
        None,
    )
    waiting_offer_exists = any((offer.status or "") in PENDING_OFFER_STATUSES for offer in company.offers)
    active_sample_exists = any((sample.status or "") in ACTIVE_SAMPLE_ALERT_STATUSES for sample in company.samples)
    if not any((active_opportunity, waiting_offer_exists, active_sample_exists)):
        return None

    has_planned_next_action = any(
        action.next_action_date and action.next_action_date >= today for action in company.actions
    )
    if has_planned_next_action:
        return None

    latest_action_date = max((action.created_at.date() for action in company.actions), default=None)
    if latest_action_date and (today - latest_action_date).days < NEXT_ACTION_MISSING_DAYS:
        return None

    reference_days = (today - latest_action_date).days if latest_action_date else NEXT_ACTION_MISSING_DAYS
    detail = "Aktif ticari süreç bulunuyor ancak ileriye dönük bir takip tarihi planlanmamış."
    secondary_action_key = ""
    secondary_action_label = ""
    contact_id: int | None = None
    opportunity_id: int | None = None
    if active_opportunity:
        detail = (
            f"{active_opportunity.title} fırsatı açık durumda ancak planlı sonraki aksiyon görünmüyor."
        )
        secondary_action_key = "open_opportunity"
        secondary_action_label = "Fırsatı Aç"
        contact_id = active_opportunity.contact_id
        opportunity_id = active_opportunity.id

    return FollowUpAlert(
        rule_key="missing_next_action",
        rule_label="Sonraki Aksiyon Eksik",
        priority=40,
        age_days=reference_days,
        company_id=company.id,
        company_name=company.name,
        company_priority=company.priority,
        title="Sonraki aksiyon planı eksik",
        description=detail,
        primary_action_key="create_action",
        primary_action_label="Aksiyon Oluştur",
        secondary_action_key=secondary_action_key,
        secondary_action_label=secondary_action_label,
        contact_id=contact_id,
        opportunity_id=opportunity_id,
        suggested_note=(
            "Aktif satış süreci için net bir sonraki adım planlanmamış. Güncel karar ve sorumluluk teyit edilecek."
        ),
        suggested_next_action="Sonraki adımı planla",
        suggested_next_action_date=today + timedelta(days=1),
    )


def _build_missing_ai_alert(
    company: Company,
    field_values: dict[str, str],
) -> FollowUpAlert | None:
    is_active = company.priority >= 4 or bool(
        company.actions or company.offers or company.samples or company.opportunities
    )
    if not is_active or _has_meaningful_ai_content(field_values):
        return None
    return FollowUpAlert(
        rule_key="missing_ai_analysis",
        rule_label="AI Analizi Eksik",
        priority=60,
        age_days=0,
        company_id=company.id,
        company_name=company.name,
        company_priority=company.priority,
        title="AI analizi güncellenmeli",
        description=(
            "Şirket için operasyonel hareket var ancak yapay zekâ analizi alanı henüz boş veya çok sınırlı."
        ),
        primary_action_key="open_ai",
        primary_action_label="AI Analizini Aç",
    )


def _action_still_requires_followup(actions: list[Action], target_action: Action) -> bool:
    if not target_action.next_action_date:
        return False
    for action in actions:
        if action.id == target_action.id:
            continue
        if action.created_at.date() < target_action.next_action_date:
            continue
        if target_action.contact_id is not None and action.contact_id in {None, target_action.contact_id}:
            return False
        if target_action.contact_id is None:
            return False
    return True


def _has_recent_action(actions: list[Action], reference_date: date, contact_id: int | None = None) -> bool:
    for action in actions:
        if action.created_at.date() < reference_date:
            continue
        if contact_id is not None:
            if action.contact_id in {None, contact_id}:
                return True
            continue
        return True
    return False


def _has_meaningful_ai_content(field_values: dict[str, str]) -> bool:
    combined_text = " ".join((field_values.get(key, "") or "").strip() for key in AI_TEXT_KEYS).strip()
    score_text = (field_values.get(AI_SCORE_KEY, "") or "").strip()
    return len(combined_text) >= 40 or bool(score_text)


def _display_value(value: str | None) -> str:
    display_map = {
        "Hazirlaniyor": "Hazırlanıyor",
        "Gonderildi": "Gönderildi",
        "Ulasti": "Ulaştı",
        "Geri Donus Bekleniyor": "Geri Dönüş Bekleniyor",
        "Gorusuluyor": "Görüşülüyor",
    }
    if not value:
        return "-"
    return display_map.get(value, value)
