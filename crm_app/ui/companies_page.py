from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import urlparse

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QDoubleValidator, QFont, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QInputDialog,
    QMessageBox,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from crm_app.models import Company, FieldDefinition, Offer, Sample
from crm_app.services.action_service import create_action, get_action, update_action
from crm_app.services.company_service import (
    create_company,
    delete_company,
    get_company,
    list_companies,
    update_company,
)
from crm_app.services.export_service import export_rows
from crm_app.services.followup_service import FollowUpAlert, get_company_followup_alerts
from crm_app.services.contact_service import create_contact, get_contact, update_contact
from crm_app.services.field_service import (
    COMPANY_BUSINESS_FIELDS,
    COMPANY_COMMERCIAL_FIELDS,
    COMPANY_AI_FIELDS,
    COMPANY_PROSPECTING_FIELDS,
    create_field_definition,
    delete_field_definition,
    ensure_company_ai_fields,
    ensure_company_business_fields,
    get_field_values,
    get_field_values_map,
    list_field_definitions,
    move_field_definition,
    parse_options,
    save_field_values,
    update_field_definition,
)
from crm_app.services.import_service import import_companies
from crm_app.services.opportunity_service import (
    create_opportunity,
    find_related_open_opportunity,
    get_opportunity,
    update_opportunity,
)
from crm_app.services.offer_service import create_offer, get_offer, split_offer_note, update_offer
from crm_app.services.sample_service import create_sample, get_sample, update_sample
from crm_app.ui.action_form import ActionFormDialog
from crm_app.ui.bulk_actions import (
    BulkDateDialog,
    confirm_bulk_action,
    create_bulk_action_controls,
    show_bulk_result,
    update_bulk_action_controls,
)
from crm_app.ui.contact_form import ContactFormDialog
from crm_app.ui.dynamic_fields import DynamicFieldsSection
from crm_app.ui.field_definition_form import FieldDefinitionFormDialog
from crm_app.ui.layout_helpers import create_scroll_area
from crm_app.ui.list_page_helpers import (
    create_list_page_toolbar,
    create_list_table_card,
    set_table_empty_state,
)
from crm_app.ui.list_preferences import (
    ListPagePreferences,
    get_selected_row_identifiers,
    get_ui_settings,
    set_row_identifier,
)
from crm_app.ui.offer_form import OfferFormDialog
from crm_app.ui.opportunity_form import OpportunityFormDialog
from crm_app.ui.priority_helpers import create_priority_label, set_priority_table_cell
from crm_app.ui.sample_form import SampleFormDialog
from crm_app.ui.surface_helpers import SurfacePanel, create_compact_stat_card
from crm_app.ui.styles import (
    apply_shadow,
    configure_table,
    create_content_card,
    create_page_header,
    create_toolbar_frame,
    set_button_role,
    style_dialog_buttons,
)
from crm_app.utils.app_paths import get_default_export_path, get_default_import_dir

_log_company_ops = logging.getLogger(__name__)


class CompanyDialog(QDialog):
    def __init__(self, company: Company | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Şirket")
        self.setMinimumSize(720, 760)
        self.company = company

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header_card = QFrame()
        header_card.setObjectName("DialogCard")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(6)
        apply_shadow(header_card, blur=14, y_offset=2, alpha=10)

        title = QLabel("Şirket Bilgileri")
        title.setObjectName("DialogTitle")
        subtitle = QLabel("Şirket kaydını, iletişim kanallarını ve ticari bilgileri düzenleyin.")
        subtitle.setObjectName("DialogSubtitle")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        scroll_area, _scroll_content, scroll_layout = create_scroll_area(max_content_width=920)

        self.name_input = QLineEdit(company.name if company else "")
        self.country_input = QLineEdit(company.country if company else "")
        self.city_input = QLineEdit(company.city if company else "")
        self.website_input = QLineEdit(company.website if company else "")
        self.linkedin_input = QLineEdit(company.linkedin if company else "")
        self.priority_input = QSpinBox()
        self.priority_input.setRange(1, 5)
        self.priority_input.setValue(company.priority if company else 3)

        ensure_company_business_fields()
        business_keys = {config["field_key"] for config in COMPANY_BUSINESS_FIELDS if config["field_key"] not in {item["field_key"] for item in COMPANY_AI_FIELDS}}
        self.business_dynamic_fields = DynamicFieldsSection(
            "company",
            entity_id=company.id if company else None,
            show_header=False,
            included_keys=business_keys,
            parent=self,
        )
        self.extra_dynamic_fields = DynamicFieldsSection(
            "company",
            entity_id=company.id if company else None,
            show_header=False,
            excluded_keys=business_keys | {item["field_key"] for item in COMPANY_AI_FIELDS},
            parent=self,
        )
        self.dynamic_sections = [section for section in [self.business_dynamic_fields, self.extra_dynamic_fields] if section.has_fields()]

        temel_form = QFormLayout()
        temel_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        temel_form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        temel_form.setHorizontalSpacing(18)
        temel_form.setVerticalSpacing(12)
        temel_form.addRow("Şirket Adı", self.name_input)
        temel_form.addRow("Ülke", self.country_input)
        temel_form.addRow("Şehir", self.city_input)
        temel_form.addRow("Öncelik", self.priority_input)
        scroll_layout.addWidget(
            self._create_form_section(
                "Temel Bilgiler",
                "Şirketin ana kimlik ve segment bilgilerini girin.",
                temel_form,
            )
        )

        link_form = QFormLayout()
        link_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        link_form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        link_form.setHorizontalSpacing(18)
        link_form.setVerticalSpacing(12)
        link_form.addRow("Web Sitesi", self.website_input)
        link_form.addRow("LinkedIn", self.linkedin_input)
        scroll_layout.addWidget(
            self._create_form_section(
                "Bağlantılar",
                "Şirketin doğrulanabilir dijital kanallarını ekleyin.",
                link_form,
            )
        )

        if self.business_dynamic_fields.has_fields():
            scroll_layout.addWidget(
                self._create_form_section(
                    "Ticari Bilgiler",
                    "Kaynak, ürün uygunluğu ve ticari değerlendirme alanlarını doldurun.",
                    self.business_dynamic_fields,
                )
            )

        if self.extra_dynamic_fields.has_fields():
            scroll_layout.addWidget(
                self._create_form_section(
                    "Ek Alanlar",
                    "Alan Yönetimi üzerinden tanımlanan diğer alanları burada tamamlayın.",
                    self.extra_dynamic_fields,
                )
            )

        scroll_layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        style_dialog_buttons(buttons)

        footer_card = QFrame()
        footer_card.setObjectName("DialogCard")
        footer_layout = QHBoxLayout(footer_card)
        footer_layout.setContentsMargins(16, 12, 16, 12)
        footer_layout.addStretch()
        footer_layout.addWidget(buttons)

        layout.addWidget(header_card)
        layout.addWidget(scroll_area, 1)
        layout.addWidget(footer_card)

    def _create_form_section(self, title: str, subtitle: str, content: Any) -> QFrame:
        card = create_content_card()
        section_layout = QVBoxLayout(card)
        section_layout.setContentsMargins(16, 16, 16, 16)
        section_layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("SectionSubtitle")
        subtitle_label.setWordWrap(True)

        section_layout.addWidget(title_label)
        section_layout.addWidget(subtitle_label)
        if isinstance(content, QFormLayout):
            section_layout.addLayout(content)
        else:
            section_layout.addWidget(content)
        return card

    def get_data(self) -> dict[str, Any]:
        custom_values: dict[str, object] = {}
        for section in self.dynamic_sections:
            custom_values.update(section.get_values())
        return {
            "name": self.name_input.text().strip(),
            "country": self.country_input.text().strip(),
            "city": self.city_input.text().strip(),
            "website": self.website_input.text().strip(),
            "linkedin": self.linkedin_input.text().strip(),
            "priority": self.priority_input.value(),
            "custom_values": custom_values,
        }

    def accept(self) -> None:
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Şirket adı zorunludur.")
            return
        for section in self.dynamic_sections:
            error_message = section.validate()
            if error_message:
                QMessageBox.warning(self, "Eksik Bilgi", error_message)
                return
        super().accept()


class CompanyDetailDialog(QDialog):
    SPLITTER_SETTINGS_KEY = "company_operations/workspace_splitter_sizes"
    DEFAULT_SPLITTER_SIZES = [840, 360]
    MIN_PRIMARY_RATIO = 0.60
    MAX_PRIMARY_RATIO = 0.80

    AI_GENERAL_HEADING = "Genel Değerlendirme"
    AI_RISKS_HEADING = "Riskler"
    AI_OPPORTUNITIES_HEADING = "Fırsatlar"

    def __init__(self, company: Company, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.company_id = company.id
        self.company = company
        self.contact_items = []
        self.action_items = []
        self.offer_items = []
        self.sample_items = []
        self.opportunity_items = []
        self.custom_field_definitions: list[FieldDefinition] = []
        self.commercial_field_definitions: list[FieldDefinition] = []
        self.ai_field_definitions: list[FieldDefinition] = []
        self.business_field_definitions: list[FieldDefinition] = []
        self.company_field_values: dict[str, str] = {}
        self.setWindowTitle("Şirket Operasyon Görünümü")
        self.setMinimumSize(1180, 860)
        self._splitter_restored = False

        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(14, 14, 14, 14)
        self.root_layout.setSpacing(12)

        self.root_layout.addWidget(
            create_page_header(
                "Şirket Operasyon Alanı",
                "Seçili şirket için tüm operasyonel hareketleri sekmeli yapıda yönetin.",
            )
        )

        self.company_name_label = QLabel()
        self.company_name_label.setObjectName("SectionTitle")
        self.company_helper_label = QLabel("Şirket profili, ilişkiler ve ticari süreçler")
        self.company_helper_label.setObjectName("SectionSubtitle")
        self.priority_chip = QLabel()
        self.priority_chip.setObjectName("PriorityPill")
        self.priority_chip.setTextFormat(Qt.TextFormat.RichText)

        self.info_rail_scroll, _info_rail_content, info_rail_layout = create_scroll_area(spacing=10)
        self.info_rail_scroll.setObjectName("CompanyOperationsInfoRail")
        self.info_rail_scroll.setMinimumWidth(330)
        self.info_rail_scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        self.identity_frame = create_toolbar_frame()
        self.identity_frame.setProperty("header_role", "summary")
        self.identity_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.identity_frame.setMinimumHeight(124)
        apply_shadow(self.identity_frame, blur=12, y_offset=2, alpha=8)
        identity_layout = QGridLayout(self.identity_frame)
        identity_layout.setContentsMargins(12, 12, 12, 12)
        identity_layout.setHorizontalSpacing(12)
        identity_layout.setVerticalSpacing(8)
        self.summary_value_labels: dict[str, QLabel] = {}
        summary_fields = [
            ("Ülke", "country"),
            ("Şehir", "city"),
            ("Çalışan Sayısı", "calisan_sayisi"),
            ("Sektör", "sektor"),
            ("Kaynak", "kaynak"),
        ]
        for _index, (_label_text, key) in enumerate(summary_fields):
            value = QLabel("-")
            value.setObjectName("SummaryValue")
            if key in {"sektor", "kaynak"}:
                value.setProperty("context", "summary-supporting")
            value.setWordWrap(True)
            self.summary_value_labels[key] = value
        identity_layout.addWidget(self.company_name_label, 0, 0, 1, 2)
        identity_layout.addWidget(self.company_helper_label, 1, 0, 1, 2)
        for index, (label_text, key) in enumerate(summary_fields):
            column = index % 2
            row = 2 + (index // 2) * 2
            title = self._make_meta_title(label_text)
            value = self.summary_value_labels[key]
            identity_layout.addWidget(title, row, column)
            identity_layout.addWidget(value, row + 1, column)

        self.links_frame = SurfacePanel(
            "Bağlantılar",
            "Web ve LinkedIn erişimleri",
            surface="content",
        )
        self.links_frame.setProperty("header_role", "actions")
        self.links_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.links_frame.setMinimumHeight(108)
        apply_shadow(self.links_frame, blur=16, y_offset=3, alpha=12)
        self.link_actions_frame = QWidget()
        self.link_actions_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.link_actions_layout = QVBoxLayout(self.link_actions_frame)
        self.link_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.link_actions_layout.setSpacing(8)
        self.website_row = self._create_link_action_row("Web Sitesi")
        self.linkedin_row = self._create_link_action_row("LinkedIn")
        self.link_actions_layout.addWidget(self.website_row["container"])
        self.link_actions_layout.addWidget(self.linkedin_row["container"])
        self.links_frame.body_layout.addWidget(self.link_actions_frame)
        self.links_frame.layout().setContentsMargins(12, 12, 12, 12)
        self.links_frame.layout().setSpacing(6)
        self.links_frame.body_layout.setSpacing(6)

        self.custom_fields_summary_label = QLabel()
        self.custom_fields_summary_label.setObjectName("PageSubtitle")
        self.custom_fields_summary_label.setWordWrap(True)

        self.top_support_frame = SurfacePanel(
            "Operasyon Özeti",
            "Öncelik ve görünür alan görünümünü tek bakışta özetleyin.",
            surface="toolbar",
        )
        self.top_support_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.top_support_frame.setMinimumHeight(92)
        support_priority_row = QHBoxLayout()
        support_priority_row.setContentsMargins(0, 0, 0, 0)
        support_priority_row.setSpacing(8)
        support_priority_label = QLabel("Öncelik")
        support_priority_label.setObjectName("SummaryLabel")
        support_priority_row.addWidget(support_priority_label)
        support_priority_row.addWidget(self.priority_chip, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        support_priority_row.addStretch(1)
        self.top_support_frame.body_layout.addLayout(support_priority_row)
        self.top_support_frame.body_layout.addWidget(self.custom_fields_summary_label)
        self.top_support_frame.layout().setContentsMargins(12, 12, 12, 12)
        self.top_support_frame.layout().setSpacing(6)
        self.top_support_frame.body_layout.setSpacing(6)

        self.commercial_frame = SurfacePanel(
            "Ürün Uygunluk Analizi",
            "Hedef şirketin ürün uyumu ve kullanım potansiyeli",
            surface="toolbar",
        )
        self.commercial_frame.setProperty("header_role", "decision")
        self.commercial_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.commercial_frame.setMinimumHeight(170)
        apply_shadow(self.commercial_frame, blur=12, y_offset=2, alpha=8)
        self.commercial_grid = QGridLayout()
        self.commercial_grid.setHorizontalSpacing(8)
        self.commercial_grid.setVerticalSpacing(8)
        self.commercial_value_labels: dict[str, QLabel] = {}
        for index, config in enumerate(COMPANY_COMMERCIAL_FIELDS):
            card, value = create_compact_stat_card(config["label"], surface="toolbar")
            card.layout().setContentsMargins(10, 9, 10, 9)
            card.layout().setSpacing(2)
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value.setMinimumHeight(32)
            self.commercial_grid.addWidget(card, index, 0)
            self.commercial_value_labels[config["field_key"]] = value
        self.commercial_grid.setColumnStretch(0, 1)
        self.commercial_frame.layout().setContentsMargins(12, 12, 12, 12)
        self.commercial_frame.layout().setSpacing(6)
        self.commercial_frame.body_layout.setSpacing(7)
        self.commercial_frame.body_layout.addLayout(self.commercial_grid)
        info_rail_layout.addWidget(self.identity_frame)
        info_rail_layout.addWidget(self.links_frame)
        info_rail_layout.addWidget(self.top_support_frame)
        info_rail_layout.addWidget(self.commercial_frame)
        info_rail_layout.addStretch()

        self.tabs = QTabWidget()
        self.tabs.setObjectName("WorkspaceTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.setMinimumHeight(440)
        self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.overview_tab, overview_layout = self._create_scroll_tab()

        self.kpi_card = create_content_card()
        self.kpi_card.setProperty("workspace_role", "kpi-strip")
        kpi_layout = QGridLayout(self.kpi_card)
        kpi_layout.setContentsMargins(14, 12, 14, 12)
        kpi_layout.setHorizontalSpacing(12)
        kpi_layout.setVerticalSpacing(10)
        self.kpi_labels: dict[str, QLabel] = {}
        kpi_items = [
            ("contacts", "Kişi Sayısı"),
            ("actions", "Aksiyon Sayısı"),
            ("offers", "Teklif Sayısı"),
            ("samples", "Numune Sayısı"),
            ("opportunities", "Fırsat Sayısı"),
        ]
        for index, (key, title) in enumerate(kpi_items):
            block_frame = QFrame()
            block_frame.setObjectName("ToolbarCard")
            block_frame.setProperty("workspace_role", "kpi-block")
            block_layout = QVBoxLayout(block_frame)
            block_layout.setContentsMargins(12, 10, 12, 10)
            block_layout.setSpacing(2)
            title_label = QLabel(title)
            title_label.setObjectName("SectionSubtitle")
            value_label = QLabel("0")
            value_label.setObjectName("SectionTitle")
            block_layout.addWidget(title_label)
            block_layout.addWidget(value_label)
            kpi_layout.addWidget(block_frame, 0, index)
            kpi_layout.setColumnStretch(index, 1)
            self.kpi_labels[key] = value_label

        action_buttons = [
            ("Yeni Kişi", self._open_contact_form, "secondary"),
            ("Yeni Aksiyon", self._open_action_form, "primary"),
            ("Yeni Teklif", self._open_offer_form, "secondary"),
            ("Yeni Numune", self._open_sample_form, "secondary"),
            ("Yeni Fırsat", self._open_opportunity_form, "secondary"),
        ]
        quick_action_widgets: list[QWidget] = []
        for text, handler, role in action_buttons:
            button = QPushButton(text)
            set_button_role(button, role)
            button.clicked.connect(handler)
            quick_action_widgets.append(button)
        self.quick_actions_card = SurfacePanel(
            "Hızlı İşlemler",
            "İlgili kayıtları tek alandan hızlıca oluşturun.",
            surface="toolbar",
        )
        self.quick_actions_card.setProperty("workspace_role", "quick-actions")
        quick_actions_grid = QGridLayout()
        quick_actions_grid.setContentsMargins(0, 2, 0, 0)
        quick_actions_grid.setHorizontalSpacing(8)
        quick_actions_grid.setVerticalSpacing(8)
        for index, button in enumerate(quick_action_widgets):
            button.setToolTip("Seçili şirket için ilgili kaydı hızlıca oluşturun.")
            quick_actions_grid.addWidget(button, index // 2, index % 2)
        quick_actions_grid.setColumnStretch(0, 1)
        quick_actions_grid.setColumnStretch(1, 1)
        self.quick_actions_card.body_layout.setSpacing(10)
        self.quick_actions_card.body_layout.addLayout(quick_actions_grid)

        self.next_step_card = SurfacePanel(
            "Öncelikli Sonraki Adım",
            "Satış akışındaki en kritik hamleyi görün ve hemen aksiyona dönüştürün.",
            surface="toolbar",
        )
        self.next_step_card.setProperty("workspace_role", "focus")
        self.next_step_card.body_layout.setSpacing(8)
        self.next_step_reason = QLabel("-")
        self.next_step_reason.setObjectName("PageEyebrow")
        self.next_step_title = QLabel("-")
        self.next_step_title.setObjectName("SectionTitle")
        self.next_step_detail = QLabel("-")
        self.next_step_detail.setObjectName("SectionSubtitle")
        self.next_step_detail.setWordWrap(True)
        self.next_step_actions_row = QHBoxLayout()
        self.next_step_actions_row.setContentsMargins(0, 2, 0, 0)
        self.next_step_actions_row.setSpacing(8)
        self.next_step_primary_button = QPushButton("Takip Aksiyonu Oluştur")
        self.next_step_secondary_button = QPushButton("AI Analizini Aç")
        set_button_role(self.next_step_primary_button, "primary")
        set_button_role(self.next_step_secondary_button, "secondary")
        self.current_next_step_action = "create_action"
        self.current_next_step_secondary_action = "open_ai"
        self.current_next_step_alert: FollowUpAlert | None = None
        self.next_step_primary_button.clicked.connect(self._trigger_current_next_step_action)
        self.next_step_secondary_button.clicked.connect(self._trigger_current_secondary_action)
        self.next_step_actions_row.addWidget(self.next_step_primary_button)
        self.next_step_actions_row.addWidget(self.next_step_secondary_button)
        self.next_step_actions_row.addStretch(1)
        self.next_step_card.body_layout.addWidget(self.next_step_reason)
        self.next_step_card.body_layout.addWidget(self.next_step_title)
        self.next_step_card.body_layout.addWidget(self.next_step_detail)
        self.next_step_card.body_layout.addLayout(self.next_step_actions_row)

        self.overview_actions_table, overview_actions_card = self._create_table_section(
            "Son Aksiyonlar",
            "Güncel temaslar ve takipler",
            ["Tarih", "Kişi", "Aksiyon", "Sonraki Adım"],
        )
        self.overview_actions_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.overview_actions_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.overview_actions_table.itemDoubleClicked.connect(self._edit_selected_overview_action)
        overview_actions_card.setProperty("workspace_role", "operations")
        overview_actions_card.setMinimumHeight(300)
        apply_shadow(overview_actions_card, blur=12, y_offset=2, alpha=8)
        self.overview_opportunities_table, overview_opportunities_card = self._create_table_section(
            "Açık Fırsatlar",
            "Şirketin aktif pipeline görünümü",
            ["Fırsat", "Aşama", "Beklenen Tutar", "Kapanış"],
        )
        self.overview_opportunities_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.overview_opportunities_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.overview_opportunities_table.itemDoubleClicked.connect(self._edit_selected_overview_opportunity)
        overview_opportunities_card.setProperty("workspace_role", "operations")
        overview_opportunities_card.setMinimumHeight(300)
        apply_shadow(overview_opportunities_card, blur=12, y_offset=2, alpha=8)

        overview_focus_row = QHBoxLayout()
        overview_focus_row.setContentsMargins(0, 0, 0, 0)
        overview_focus_row.setSpacing(12)
        overview_focus_row.addWidget(self.next_step_card, 5)
        overview_focus_row.addWidget(self.quick_actions_card, 4)

        overview_tables_row = QHBoxLayout()
        overview_tables_row.setContentsMargins(0, 0, 0, 0)
        overview_tables_row.setSpacing(12)
        overview_tables_row.addWidget(overview_actions_card, 5)
        overview_tables_row.addWidget(overview_opportunities_card, 4)

        overview_layout.addWidget(self.kpi_card)
        overview_layout.addLayout(overview_focus_row)
        overview_layout.addLayout(overview_tables_row)
        overview_layout.addStretch()

        self.contacts_table, contacts_tab = self._create_record_tab(
            "Kişiler",
            "Şirket ile ilişkili tüm kişi kayıtları",
            ["Ad Soyad", "Ünvan", "Email", "Telefon"],
            self._open_contact_form,
            self._edit_selected_contact,
        )
        self.actions_table, actions_tab = self._create_record_tab(
            "Aksiyonlar",
            "Şirket bazlı tüm temaslar ve takipler",
            ["Tarih", "Kişi", "Aksiyon Tipi", "Kanal", "Sonraki Aksiyon"],
            self._open_action_form,
            self._edit_selected_action,
        )
        self.opportunities_table, opportunities_tab = self._create_record_tab(
            "Fırsatlar",
            "Şirketin pipeline kayıtları",
            ["Fırsat", "Aşama", "Beklenen Tutar", "Kapanış", "Kişi"],
            self._open_opportunity_form,
            self._edit_selected_opportunity,
        )
        self.offers_table, offers_tab = self._create_record_tab(
            "Teklifler",
            "Ticari teklifler ve durum özeti",
            ["Teklif No", "Tarih", "Kişi", "Durum", "Açıklama"],
            self._open_offer_form,
            self._edit_selected_offer,
        )
        self.samples_table, samples_tab = self._create_record_tab(
            "Numuneler",
            "Numune kayıtları ve geri dönüş süreçleri",
            ["Ürün", "Adet", "Gönderim Tarihi", "Durum", "Kişi"],
            self._open_sample_form,
            self._edit_selected_sample,
        )
        self.custom_fields_tab = self._create_custom_fields_tab()
        self.ai_analysis_tab = self._create_ai_analysis_tab()

        self.tabs.addTab(self.overview_tab, "Genel Bakış")
        self.tabs.addTab(contacts_tab, "Kişiler")
        self.tabs.addTab(actions_tab, "Aksiyonlar")
        self.tabs.addTab(opportunities_tab, "Fırsatlar")
        self.tabs.addTab(offers_tab, "Teklifler")
        self.tabs.addTab(samples_tab, "Numuneler")
        self.tabs.addTab(self.ai_analysis_tab, "Yapay Zekâ Analizi")
        self.tabs.addTab(self.custom_fields_tab, "Özel Alanlar")

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setObjectName("CompanyOperationsSplitter")
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.setHandleWidth(6)
        self.main_splitter.setOpaqueResize(True)
        self.main_splitter.addWidget(self.tabs)
        self.main_splitter.addWidget(self.info_rail_scroll)
        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 0)
        self.main_splitter.splitterMoved.connect(self._save_splitter_sizes)

        self.root_layout.addWidget(self.main_splitter, 1)

        self.refresh_content()
    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if not self._splitter_restored:
            self._restore_splitter_sizes()
            self._splitter_restored = True

    def _make_meta_title(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SummaryLabel")
        return label

    def _restore_splitter_sizes(self) -> None:
        settings = get_ui_settings()
        raw_sizes = settings.value(self.SPLITTER_SETTINGS_KEY, [])
        sizes: list[int] = []
        if isinstance(raw_sizes, list):
            for value in raw_sizes[:2]:
                try:
                    sizes.append(int(value))
                except (TypeError, ValueError):
                    sizes = []
                    break
        elif raw_sizes:
            try:
                sizes = [int(part) for part in str(raw_sizes).split(",")[:2]]
            except ValueError:
                sizes = []

        if len(sizes) == 2 and all(size > 0 for size in sizes):
            self.main_splitter.setSizes(self._sanitize_splitter_sizes(sizes))
            return

        self.main_splitter.setSizes(self._sanitize_splitter_sizes(self.DEFAULT_SPLITTER_SIZES))

    def _save_splitter_sizes(self, *_args: object) -> None:
        get_ui_settings().setValue(
            self.SPLITTER_SETTINGS_KEY,
            self._sanitize_splitter_sizes(self.main_splitter.sizes()),
        )

    def _sanitize_splitter_sizes(self, sizes: list[int]) -> list[int]:
        if len(sizes) != 2:
            return self.DEFAULT_SPLITTER_SIZES[:]

        primary_size, rail_size = sizes
        if primary_size <= 0 or rail_size <= 0:
            return self.DEFAULT_SPLITTER_SIZES[:]

        total = primary_size + rail_size
        if total <= 0:
            return self.DEFAULT_SPLITTER_SIZES[:]

        primary_ratio = primary_size / total
        primary_ratio = max(self.MIN_PRIMARY_RATIO, min(self.MAX_PRIMARY_RATIO, primary_ratio))
        primary_size = int(total * primary_ratio)
        rail_size = max(total - primary_size, 1)
        return [primary_size, rail_size]

    def _create_link_action_row(self, label_text: str) -> dict[str, QWidget | QLabel | QPushButton]:
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        label = QLabel(label_text)
        label.setObjectName("SummaryLabel")
        label.setMinimumWidth(82)
        label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        descriptor = QLabel("-")
        descriptor.setObjectName("SummaryValue")
        descriptor.setProperty("context", "link-descriptor")
        descriptor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        descriptor.setWordWrap(False)
        descriptor.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        actions_container = QWidget()
        actions_container.setProperty("context", "link-actions")
        actions_container.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        actions_layout = QHBoxLayout(actions_container)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(6)

        open_button = QPushButton("Aç")
        copy_button = QPushButton("Kopyala")
        set_button_role(open_button, "ghost")
        set_button_role(copy_button, "ghost")
        open_button.setProperty("context", "link-action")
        copy_button.setProperty("context", "link-action")
        open_button.setToolTip("Bağlantıyı aç")
        copy_button.setToolTip("Bağlantıyı kopyala")
        open_button.setMinimumHeight(28)
        copy_button.setMinimumHeight(28)
        open_button.setMinimumWidth(50)
        copy_button.setMinimumWidth(72)
        open_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        copy_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        open_button.clicked.connect(
            lambda _checked=False, button=open_button: self._open_external_link(button.property("link_url") or "")
        )
        copy_button.clicked.connect(
            lambda _checked=False, button=copy_button: self._copy_external_link(
                button.property("link_url") or "",
                button,
            )
        )

        actions_layout.addWidget(open_button)
        actions_layout.addWidget(copy_button)
        layout.addWidget(label)
        layout.addWidget(descriptor, 1)
        layout.addSpacing(4)
        layout.addWidget(actions_container, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return {
            "container": container,
            "label": label,
            "descriptor": descriptor,
            "actions_container": actions_container,
            "open_button": open_button,
            "copy_button": copy_button,
        }

    def _create_record_tab(
        self,
        title: str,
        subtitle: str,
        headers: list[str],
        add_handler: Any,
        edit_handler: Any,
    ) -> tuple[QTableWidget, QWidget]:
        tab, layout = self._create_scroll_tab()

        add_button = QPushButton("Yeni")
        edit_button = QPushButton("Düzenle")
        refresh_button = QPushButton("Yenile")
        set_button_role(add_button, "secondary")
        set_button_role(edit_button, "secondary")
        set_button_role(refresh_button, "ghost")
        add_button.clicked.connect(add_handler)
        edit_button.clicked.connect(edit_handler)
        refresh_button.clicked.connect(self.refresh_content)

        table, card = self._create_table_section(
            title,
            subtitle,
            headers,
            trailing_widgets=[add_button, edit_button, refresh_button],
        )

        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.itemDoubleClicked.connect(edit_handler)

        layout.addWidget(card)
        layout.addStretch()
        return table, tab

    def _create_scroll_tab(self) -> tuple[QWidget, QVBoxLayout]:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll_area, _scroll_content, content_layout = create_scroll_area(spacing=12)
        content_layout.setContentsMargins(0, 10, 0, 0)
        layout.addWidget(scroll_area)
        return tab, content_layout

    def _create_table_section(
        self,
        title: str,
        subtitle: str,
        headers: list[str],
        trailing_widgets: list[QWidget] | None = None,
    ) -> tuple[QTableWidget, QFrame]:
        card = SurfacePanel(title, subtitle, trailing_widgets=trailing_widgets)

        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        configure_table(table)
        card.body_layout.addWidget(table)
        return table, card

    def _create_custom_fields_tab(self) -> QWidget:
        tab, layout = self._create_scroll_tab()

        self.manage_custom_fields_button = QPushButton("Özel Alanları Düzenle")
        self.manage_custom_fields_button.setCheckable(True)
        set_button_role(self.manage_custom_fields_button, "ghost")
        self.manage_custom_fields_button.toggled.connect(self._toggle_custom_fields_manage_mode)
        display_card = SurfacePanel(
            "Özel Alanlar",
            "Şirket özel alanlarını düzenli biçimde inceleyin ve hızlıca yönetin.",
            trailing_widgets=[self.manage_custom_fields_button],
        )

        self.custom_fields_grid = QGridLayout()
        self.custom_fields_grid.setHorizontalSpacing(22)
        self.custom_fields_grid.setVerticalSpacing(12)
        display_card.body_layout.addLayout(self.custom_fields_grid)
        display_card.body_layout.addStretch()

        self.manage_fields_table = QTableWidget()
        self.manage_fields_table.setColumnCount(4)
        self.manage_fields_table.setHorizontalHeaderLabels(["Sıra", "Alan", "Tip", "Durum"])
        self.manage_fields_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.manage_fields_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.manage_fields_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.manage_fields_table.verticalHeader().setVisible(False)
        self.manage_fields_table.horizontalHeader().setStretchLastSection(True)
        configure_table(self.manage_fields_table)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)
        add_button = QPushButton("Yeni Alan Ekle")
        rename_button = QPushButton("Alanı Yeniden Adlandır")
        toggle_button = QPushButton("Gizle / Göster")
        remove_button = QPushButton("Kaldır")
        up_button = QPushButton("Yukarı")
        down_button = QPushButton("Aşağı")
        advanced_button = QPushButton("Alan Yönetimi")
        for button, role in [
            (add_button, "primary"),
            (rename_button, "secondary"),
            (toggle_button, "ghost"),
            (remove_button, "danger"),
            (up_button, "ghost"),
            (down_button, "ghost"),
            (advanced_button, "secondary"),
        ]:
            set_button_role(button, role)

        add_button.clicked.connect(self._add_custom_field_definition)
        rename_button.clicked.connect(self._rename_custom_field_definition)
        toggle_button.clicked.connect(self._toggle_selected_custom_field_visibility)
        remove_button.clicked.connect(self._delete_selected_custom_field_definition)
        up_button.clicked.connect(lambda: self._move_selected_custom_field_definition("up"))
        down_button.clicked.connect(lambda: self._move_selected_custom_field_definition("down"))
        advanced_button.clicked.connect(self._go_to_field_management_page)

        self.custom_fields_manage_card = SurfacePanel(
            "Hızlı Alan Yönetimi",
            "Alan tipi, teknik anahtar ve seçenekler için ana Alan Yönetimi ekranını kullanın.",
            surface="toolbar",
        )
        for button in [add_button, rename_button, toggle_button, remove_button, up_button, down_button, advanced_button]:
            actions_row.addWidget(button)
        actions_row.addStretch()

        self.custom_fields_manage_card.body_layout.addWidget(self.manage_fields_table)
        self.custom_fields_manage_card.body_layout.addLayout(actions_row)

        self.custom_fields_manage_card.hide()
        layout.addWidget(display_card)
        layout.addWidget(self.custom_fields_manage_card)
        layout.addStretch()
        return tab

    def _create_ai_analysis_tab(self) -> QWidget:
        tab, layout = self._create_scroll_tab()

        summary_meta_card, self.ai_last_updated_value = create_compact_stat_card("Son Analiz Tarihi")
        summary_score_card, self.ai_score_summary_value = create_compact_stat_card(
            "AI Uygunluk Skoru",
            value_object_name="PageTitle",
        )
        self.ai_general_input = QTextEdit()
        self.ai_general_input.setPlaceholderText("Şirketin genel potansiyelini, karar verici yapısını ve ticari özetini yazın...")
        self.ai_general_input.setMinimumHeight(150)
        self.ai_general_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.ai_risks_input = QTextEdit()
        self.ai_risks_input.setPlaceholderText("Riskleri, itiraz noktalarını ve satış sürecini zorlaştırabilecek unsurları yazın...")
        self.ai_risks_input.setMinimumHeight(130)
        self.ai_risks_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.ai_opportunities_input = QTextEdit()
        self.ai_opportunities_input.setPlaceholderText("Fırsatları, ürün uyumunu ve büyüme ihtimallerini yazın...")
        self.ai_opportunities_input.setMinimumHeight(130)
        self.ai_opportunities_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.sales_strategy_input = QTextEdit()
        self.sales_strategy_input.setPlaceholderText("Satış yaklaşımı, iletişim dili ve teklifleme stratejisini yazın...")
        self.sales_strategy_input.setMinimumHeight(150)
        self.sales_strategy_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.recommended_next_step_input = QTextEdit()
        self.recommended_next_step_input.setPlaceholderText("Önerilen sonraki adımı veya takip aksiyonunu yazın...")
        self.recommended_next_step_input.setMinimumHeight(110)
        self.recommended_next_step_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.ai_score_input = QLineEdit()
        self.ai_score_input.setPlaceholderText("0 - 100")
        self.ai_score_input.setValidator(QDoubleValidator(0.0, 100.0, 2, self.ai_score_input))
        score_input_card = SurfacePanel("Skor Güncelle", "Skoru doğrudan düzenleyin.", surface="toolbar")
        score_input_card.body_layout.addWidget(self.ai_score_input)
        score_input_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        general_card = self._create_ai_editor_block(
            "Genel Değerlendirme",
            "Şirketin genel potansiyelini, karar yapısını ve satış resmi özetini kaydedin.",
            self.ai_general_input,
        )
        risks_card = self._create_ai_editor_block(
            "Riskler",
            "Geciktirici unsurları, itirazları ve satışta dikkat edilmesi gereken noktaları toplayın.",
            self.ai_risks_input,
        )
        opportunities_card = self._create_ai_editor_block(
            "Fırsatlar",
            "Ürün uyumu, giriş kapıları ve ticari kazanım ihtimallerini görünür kılın.",
            self.ai_opportunities_input,
        )
        strategy_card = self._create_ai_editor_block(
            "Satış Yaklaşımı",
            "İletişim dili, ticari yaklaşım ve öncelikli temas planını not edin.",
            self.sales_strategy_input,
        )
        next_step_card = self._create_ai_editor_block(
            "Önerilen Sonraki Adım",
            "Kısa vadede uygulanacak takip adımını veya önerilen aksiyonu yazın.",
            self.recommended_next_step_input,
        )
        general_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        risks_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        opportunities_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        strategy_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        next_step_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        refresh_button = QPushButton("Yenile")
        save_button = QPushButton("Kaydet")
        set_button_role(refresh_button, "ghost")
        set_button_role(save_button, "primary")
        refresh_button.setMinimumWidth(90)
        save_button.setMinimumWidth(96)
        refresh_button.clicked.connect(self._populate_ai_analysis_tab)
        save_button.clicked.connect(self._save_ai_analysis)
        actions_card = SurfacePanel("Analiz Aksiyonları", "Bu alanı yenileyin veya kaydedin.", surface="toolbar")
        actions_row = QHBoxLayout()
        actions_row.setContentsMargins(0, 0, 0, 0)
        actions_row.setSpacing(8)
        actions_row.addWidget(refresh_button)
        actions_row.addWidget(save_button)
        actions_row.addStretch(1)
        actions_card.body_layout.addLayout(actions_row)
        actions_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        summary_meta_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        summary_score_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        editorial_header = SurfacePanel(
            "Analiz Özeti",
            "Yapay zekâ değerlendirmesini okunabilir bir çalışma alanında yönetin.",
            surface="toolbar",
        )
        editorial_hint = QLabel(
            "Genel değerlendirmeyi ana yüzeyde yönetin; skor, tarih ve kayıt aksiyonlarını üst özet şeridinden kontrol edin."
        )
        editorial_hint.setObjectName("SectionSubtitle")
        editorial_hint.setWordWrap(True)
        editorial_header.body_layout.addWidget(editorial_hint)
        editorial_summary_row = QHBoxLayout()
        editorial_summary_row.setContentsMargins(0, 0, 0, 0)
        editorial_summary_row.setSpacing(12)
        editorial_summary_row.addWidget(summary_meta_card, 1)
        editorial_summary_row.addWidget(summary_score_card, 1)
        editorial_summary_row.addWidget(score_input_card, 1)
        editorial_summary_row.addWidget(actions_card, 2)
        editorial_header.body_layout.addLayout(editorial_summary_row)

        insight_row = QHBoxLayout()
        insight_row.setContentsMargins(0, 0, 0, 0)
        insight_row.setSpacing(12)
        insight_row.addWidget(risks_card, 3)
        insight_row.addWidget(opportunities_card, 2)

        action_plan_row = QHBoxLayout()
        action_plan_row.setContentsMargins(0, 0, 0, 0)
        action_plan_row.setSpacing(12)
        action_plan_row.addWidget(strategy_card, 3)
        action_plan_row.addWidget(next_step_card, 2)

        layout.addWidget(editorial_header)
        layout.addWidget(general_card)
        layout.addLayout(insight_row)
        layout.addLayout(action_plan_row)
        layout.addStretch()
        return tab

    def _create_ai_editor_block(self, title: str, subtitle: str, editor: QTextEdit) -> QFrame:
        card = SurfacePanel(title, subtitle)
        card.body_layout.addWidget(editor)
        return card

    def _trigger_current_next_step_action(self) -> None:
        self._run_next_step_action(self.current_next_step_action)

    def _trigger_current_secondary_action(self) -> None:
        if not self.current_next_step_secondary_action:
            return
        self._run_next_step_action(self.current_next_step_secondary_action)

    def _extract_ai_sections(self, raw_text: str) -> dict[str, str]:
        sections = {
            "general": "",
            "risks": "",
            "opportunities": "",
        }
        if not raw_text.strip():
            return sections

        current_key = "general"
        buffer: dict[str, list[str]] = {"general": [], "risks": [], "opportunities": []}
        heading_map = {
            self.AI_GENERAL_HEADING.lower(): "general",
            self.AI_RISKS_HEADING.lower(): "risks",
            self.AI_OPPORTUNITIES_HEADING.lower(): "opportunities",
        }
        for line in raw_text.splitlines():
            normalized = line.strip().rstrip(":").lower()
            if normalized in heading_map:
                current_key = heading_map[normalized]
                continue
            buffer[current_key].append(line)

        for key, lines in buffer.items():
            sections[key] = "\n".join(lines).strip()

        if not sections["general"] and raw_text.strip():
            sections["general"] = raw_text.strip()
        return sections

    def _compose_ai_analysis_text(self) -> str:
        sections = [
            (self.AI_GENERAL_HEADING, self.ai_general_input.toPlainText().strip()),
            (self.AI_RISKS_HEADING, self.ai_risks_input.toPlainText().strip()),
            (self.AI_OPPORTUNITIES_HEADING, self.ai_opportunities_input.toPlainText().strip()),
        ]
        blocks = [f"{title}:\n{value}" for title, value in sections if value]
        return "\n\n".join(blocks).strip()

    def _build_next_step_recommendation(self) -> FollowUpAlert | None:
        alerts = get_company_followup_alerts(self.company_id, limit=1)
        return alerts[0] if alerts else None

    def _run_next_step_action(self, action_key: str) -> None:
        alert = self.current_next_step_alert
        if action_key == "create_contact":
            self._open_contact_form()
        elif action_key == "create_opportunity":
            self._open_opportunity_form_from_alert(alert)
        elif action_key == "open_opportunity":
            self._open_alert_opportunity(alert)
        elif action_key == "open_ai":
            self.tabs.setCurrentWidget(self.ai_analysis_tab)
        else:
            self._open_action_form_from_alert(alert)

    def _open_action_form_from_alert(self, alert: FollowUpAlert | None) -> None:
        if not alert:
            self._open_action_form()
            return
        dialog = ActionFormDialog(
            initial_company_id=self.company_id,
            initial_contact_id=alert.contact_id,
            initial_record_type="Kisi" if alert.contact_id else "Sirket",
            initial_action_type=alert.suggested_action_type,
            initial_channel=alert.suggested_channel,
            initial_note=alert.suggested_note,
            initial_next_action=alert.suggested_next_action,
            initial_next_action_date=alert.suggested_next_action_date,
            parent=self,
        )
        if dialog.exec():
            create_action(dialog.get_data())
            self._after_create("Aksiyon kaydı oluşturuldu.")

    def _open_opportunity_form_from_alert(self, alert: FollowUpAlert | None) -> None:
        dialog = OpportunityFormDialog(
            initial_company_id=self.company_id,
            initial_contact_id=alert.contact_id if alert else None,
            initial_title=alert.suggested_opportunity_title if alert else "",
            initial_note=alert.suggested_opportunity_note if alert else "",
            initial_stage=alert.suggested_opportunity_stage if alert else "",
            parent=self,
        )
        if dialog.exec():
            create_opportunity(dialog.get_data())
            self._after_create("Fırsat kaydı oluşturuldu.")

    def _open_alert_opportunity(self, alert: FollowUpAlert | None) -> None:
        if not alert or not alert.opportunity_id:
            self._open_opportunity_form()
            return
        opportunity = get_opportunity(alert.opportunity_id)
        if not opportunity:
            self._open_opportunity_form()
            return
        dialog = OpportunityFormDialog(opportunity=opportunity, parent=self)
        if dialog.exec():
            update_opportunity(opportunity.id, dialog.get_data())
            self._after_create("Fırsat kaydı güncellendi.")

    def refresh_content(self) -> None:
        fresh_company = get_company(self.company_id)
        if not fresh_company:
            return

        self.company = fresh_company
        self.company_name_label.setText(self.company.name)
        self.business_field_definitions = ensure_company_business_fields()
        self.commercial_field_definitions = [
            definition
            for definition in self.business_field_definitions
            if definition.field_key in {config["field_key"] for config in COMPANY_COMMERCIAL_FIELDS}
        ]
        self.ai_field_definitions = ensure_company_ai_fields()
        self.custom_field_definitions = list_field_definitions("company")
        self.company_field_values = get_field_values("company", self.company.id)
        self._populate_company_summary_fields()
        self._configure_link_row(self.website_row, self.company.website)
        self._configure_link_row(self.linkedin_row, self.company.linkedin)
        self.link_actions_frame.setVisible(bool(self.company.website or self.company.linkedin))
        priority_label = create_priority_label(self.company.priority, font_size=11, centered=False)
        self.priority_chip.setText(priority_label.text())
        self.priority_chip.setToolTip(priority_label.toolTip())
        self._populate_commercial_analysis()
        custom_rows = self._build_custom_field_rows()
        self.custom_fields_summary_label.setText(
            f"Bu şirket için {len(custom_rows)} görünür özel alan tanımlı. Ayrıntılar için Özel Alanlar sekmesini kullanın."
            if custom_rows
            else "Bu şirket için görünür özel alan tanımı bulunmuyor."
        )

        self.kpi_labels["contacts"].setText(str(len(self.company.contacts)))
        self.kpi_labels["actions"].setText(str(len(self.company.actions)))
        self.kpi_labels["offers"].setText(str(len(self.company.offers)))
        self.kpi_labels["samples"].setText(str(len(self.company.samples)))
        self.kpi_labels["opportunities"].setText(str(len(self.company.opportunities)))

        self._populate_contacts()
        self._populate_actions()
        self._populate_opportunities()
        self._populate_offers()
        self._populate_samples()
        self._populate_overview()
        self._populate_ai_analysis_tab()
        self._populate_custom_fields_tab(custom_rows)
        self._populate_custom_fields_manager()

        parent = self.parent()
        if parent and hasattr(parent, "refresh_table"):
            parent.refresh_table()

    def _configure_link_row(self, row: dict[str, QWidget | QLabel | QPushButton], url: str) -> None:
        container = row["container"]
        descriptor = row["descriptor"]
        open_button = row["open_button"]
        copy_button = row["copy_button"]
        assert isinstance(container, QWidget)
        assert isinstance(descriptor, QLabel)
        assert isinstance(open_button, QPushButton)
        assert isinstance(copy_button, QPushButton)

        container.setVisible(bool(url))
        descriptor.setText(self._format_link_descriptor(url))
        open_button.setEnabled(bool(url))
        copy_button.setEnabled(bool(url))
        open_button.setProperty("link_url", url or "")
        copy_button.setProperty("link_url", url or "")

    def _open_external_link(self, url: str) -> None:
        if not url:
            return
        QDesktopServices.openUrl(QUrl(url))

    def _copy_external_link(self, url: str, anchor: QWidget) -> None:
        if not url:
            return
        QApplication.clipboard().setText(url)
        QToolTip.showText(anchor.mapToGlobal(anchor.rect().center()), "Bağlantı kopyalandı", anchor)

    def _format_link_descriptor(self, url: str) -> str:
        if not url:
            return "-"
        parsed = urlparse(url)
        host = (parsed.netloc or parsed.path).replace("www.", "").strip("/")
        path = parsed.path.lower()
        if "linkedin.com" in host:
            if "/company/" in path:
                return "Şirket Sayfası"
            return "LinkedIn Profili"
        return host or "Web Sitesi"

    def _commercial_field_keys(self) -> set[str]:
        return {config["field_key"] for config in COMPANY_COMMERCIAL_FIELDS}

    def _ai_field_keys(self) -> set[str]:
        return {config["field_key"] for config in COMPANY_AI_FIELDS}

    def _prospecting_field_keys(self) -> set[str]:
        return {config["field_key"] for config in COMPANY_PROSPECTING_FIELDS}

    def _business_field_keys(self) -> set[str]:
        return {config["field_key"] for config in COMPANY_BUSINESS_FIELDS}

    def _populate_company_summary_fields(self) -> None:
        self.summary_value_labels["country"].setText(self.company.country or "-")
        self.summary_value_labels["city"].setText(self.company.city or "-")
        self.summary_value_labels["sektor"].setText(self.company_field_values.get("sektor") or "-")
        self.summary_value_labels["calisan_sayisi"].setText(
            self.company_field_values.get("calisan_sayisi") or "-"
        )
        self.summary_value_labels["kaynak"].setText(self.company_field_values.get("kaynak") or "-")

    def _populate_commercial_analysis(self) -> None:
        for definition in self.commercial_field_definitions:
            if definition.field_type == "boolean":
                text = "Evet" if self.company_field_values.get(definition.field_key) == "1" else "-"
            else:
                text = self.company_field_values.get(definition.field_key) or "-"
            label = self.commercial_value_labels.get(definition.field_key)
            if label:
                label.setText(text)

    def _populate_ai_analysis_tab(self) -> None:
        ai_sections = self._extract_ai_sections(self.company_field_values.get("ai_analizi", ""))
        self.ai_general_input.setPlainText(ai_sections["general"])
        self.ai_risks_input.setPlainText(ai_sections["risks"])
        self.ai_opportunities_input.setPlainText(ai_sections["opportunities"])
        self.sales_strategy_input.setPlainText(self.company_field_values.get("satis_stratejisi", ""))
        self.recommended_next_step_input.setPlainText(
            self.company_field_values.get("onerilen_sonraki_adim", "")
        )
        score_value = self.company_field_values.get("ai_uygunluk_skoru", "")
        self.ai_score_input.setText(score_value)
        self.ai_score_summary_value.setText(score_value or "-")
        self.ai_last_updated_value.setText(
            self._format_ai_timestamp(self.company_field_values.get("ai_son_analiz_tarihi", ""))
        )

    def _format_ai_timestamp(self, raw_value: str) -> str:
        if not raw_value:
            return "-"
        try:
            timestamp = datetime.fromisoformat(raw_value)
        except ValueError:
            return raw_value
        return timestamp.strftime("%d.%m.%Y %H:%M")

    def _save_ai_analysis(self) -> None:
        score_text = self.ai_score_input.text().strip()
        if score_text:
            try:
                score_value = float(score_text)
            except ValueError:
                QMessageBox.warning(self, "Eksik Bilgi", "AI Uygunluk Skoru sayısal olmalıdır.")
                return
            if score_value < 0 or score_value > 100:
                QMessageBox.warning(self, "Eksik Bilgi", "AI Uygunluk Skoru 0 ile 100 arasında olmalıdır.")
                return

        updated_values = dict(self.company_field_values)
        updated_values.update(
            {
                "ai_analizi": self._compose_ai_analysis_text(),
                "satis_stratejisi": self.sales_strategy_input.toPlainText().strip(),
                "onerilen_sonraki_adim": self.recommended_next_step_input.toPlainText().strip(),
                "ai_uygunluk_skoru": score_text,
                "ai_son_analiz_tarihi": datetime.now().isoformat(timespec="seconds"),
            }
        )
        _log_company_ops.info(
            "CompanyDetailDialog._save_ai_analysis | company_id=%s | ai_analizi_chars=%s | "
            "strategi_chars=%s | next_step_chars=%s | score=%r",
            self.company_id,
            len(updated_values.get("ai_analizi", "") or ""),
            len(updated_values.get("satis_stratejisi", "") or ""),
            len(updated_values.get("onerilen_sonraki_adim", "") or ""),
            updated_values.get("ai_uygunluk_skoru", ""),
        )
        save_field_values("company", self.company_id, updated_values)
        self.company_field_values = get_field_values("company", self.company_id)
        _log_company_ops.info(
            "CompanyDetailDialog._save_ai_analysis after reload | company_id=%s | "
            "ai_analizi_chars=%s | keys_count=%s",
            self.company_id,
            len(self.company_field_values.get("ai_analizi", "") or ""),
            len(self.company_field_values),
        )
        self._populate_ai_analysis_tab()
        QMessageBox.information(self, "Bilgi", "Yapay zekâ analizi kaydedildi.")

    def _build_custom_field_rows(self) -> list[tuple[FieldDefinition, str]]:
        rows: list[tuple[FieldDefinition, str]] = []
        for definition in self.custom_field_definitions:
            if definition.field_key in self._business_field_keys():
                continue
            if not definition.is_visible:
                continue

            raw_value = self.company_field_values.get(definition.field_key, "")
            if definition.field_type == "boolean":
                display_value = "Evet" if raw_value == "1" else "Hayir" if raw_value else "-"
            else:
                display_value = raw_value or "-"
            rows.append((definition, display_value))
        return rows

    def _populate_table(
        self,
        table: QTableWidget,
        rows: list[list[str]],
        empty_message: str,
    ) -> None:
        table.clearContents()
        if not rows:
            action_label = None
            action_handler = None
            if table is self.contacts_table:
                action_label = "Yeni Kişi"
                action_handler = self._open_contact_form
            elif table is self.actions_table or table is self.overview_actions_table:
                action_label = "Yeni Aksiyon"
                action_handler = self._open_action_form
            elif table is self.opportunities_table or table is self.overview_opportunities_table:
                action_label = "Yeni Fırsat"
                action_handler = self._open_opportunity_form
            elif table is self.offers_table:
                action_label = "Yeni Teklif"
                action_handler = self._open_offer_form
            elif table is self.samples_table:
                action_label = "Yeni Numune"
                action_handler = self._open_sample_form
            set_table_empty_state(
                table,
                empty_message,
                action_label=action_label,
                action_handler=action_handler,
            )
            return

        table.setRowCount(len(rows))
        for row_index, values in enumerate(rows):
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(row_index, column, item)
        table.resizeColumnsToContents()

    def _populate_contacts(self) -> None:
        self.contact_items = sorted(self.company.contacts, key=lambda item: item.name.lower())
        rows = [
            [
                contact.name,
                contact.title or "-",
                contact.email or "-",
                contact.phone or "-",
            ]
            for contact in self.contact_items
        ]
        self._populate_table(
            self.contacts_table,
            rows,
            "Henüz kişi eklenmedi. İlk kişi kaydını oluşturarak karar verici haritasını netleştirin.",
        )

    def _populate_actions(self) -> None:
        self.action_items = sorted(
            self.company.actions,
            key=lambda item: item.created_at,
            reverse=True,
        )
        rows = [
            [
                action.created_at.strftime("%d.%m.%Y %H:%M"),
                action.contact.name if action.contact else "-",
                action.action_type or "-",
                action.channel or "-",
                action.next_action or "-",
            ]
            for action in self.action_items
        ]
        self._populate_table(
            self.actions_table,
            rows,
            "Henüz aksiyon kaydı yok. İlk temas veya takip aksiyonunu oluşturarak süreci başlatın.",
        )

    def _populate_opportunities(self) -> None:
        self.opportunity_items = sorted(
            self.company.opportunities,
            key=lambda item: (
                item.expected_close_date is not None,
                item.expected_close_date.toordinal()
                if item.expected_close_date
                else item.updated_at.timestamp(),
                item.updated_at.timestamp(),
            ),
            reverse=True,
        )
        rows = [
            [
                opportunity.title,
                opportunity.stage or "-",
                f"{opportunity.expected_amount:,.2f} {opportunity.currency or ''}".strip(),
                opportunity.expected_close_date.strftime("%d.%m.%Y")
                if opportunity.expected_close_date
                else "-",
                opportunity.contact.name if opportunity.contact else "-",
            ]
            for opportunity in self.opportunity_items
        ]
        self._populate_table(
            self.opportunities_table,
            rows,
            "Bu şirket için açık fırsat yok. Yeni fırsat oluşturarak satış sürecini başlatın.",
        )

    def _populate_offers(self) -> None:
        self.offer_items = sorted(
            self.company.offers,
            key=lambda item: (item.date is not None, item.date or item.id),
            reverse=True,
        )
        rows = []
        for offer in self.offer_items:
            description, _details = split_offer_note(offer.note or "")
            rows.append(
                [
                    offer.offer_no,
                    offer.date.strftime("%d.%m.%Y") if offer.date else "-",
                    offer.contact.name if offer.contact else "-",
                    offer.status or "-",
                    description or "-",
                ]
            )
        self._populate_table(
            self.offers_table,
            rows,
            "Henüz teklif kaydı yok. Ticari görüşme netleştiğinde ilk teklifi oluşturun.",
        )

    def _populate_samples(self) -> None:
        self.sample_items = sorted(
            self.company.samples,
            key=lambda item: (item.sent_date is not None, item.sent_date or item.id),
            reverse=True,
        )
        rows = [
            [
                sample.product or "-",
                str(sample.quantity),
                sample.sent_date.strftime("%d.%m.%Y") if sample.sent_date else "-",
                sample.status or "-",
                sample.contact.name if sample.contact else "-",
            ]
            for sample in self.sample_items
        ]
        self._populate_table(
            self.samples_table,
            rows,
            "Henüz numune kaydı yok. Ürün deneme süreci başladığında ilk numune kaydını açın.",
        )

    def _populate_overview(self) -> None:
        next_alert = self._build_next_step_recommendation()
        self.current_next_step_alert = next_alert
        if next_alert:
            self.next_step_reason.setText(next_alert.rule_label)
            self.next_step_title.setText(next_alert.title)
            self.next_step_detail.setText(next_alert.description)
            self.next_step_primary_button.setText(next_alert.primary_action_label)
            self.current_next_step_action = next_alert.primary_action_key
            if next_alert.secondary_action_key:
                self.current_next_step_secondary_action = next_alert.secondary_action_key
                self.next_step_secondary_button.setText(next_alert.secondary_action_label)
                self.next_step_secondary_button.setVisible(True)
            elif next_alert.primary_action_key != "open_ai":
                self.current_next_step_secondary_action = "open_ai"
                self.next_step_secondary_button.setText("AI Analizini Aç")
                self.next_step_secondary_button.setVisible(True)
            else:
                self.current_next_step_secondary_action = ""
                self.next_step_secondary_button.setVisible(False)
        else:
            self.next_step_reason.setText("Durum Özeti")
            self.next_step_title.setText("Şu anda kritik takip uyarısı yok")
            self.next_step_detail.setText(
                "Temel operasyon akışı dengede görünüyor. Yeni ticari adım planlayabilir veya AI analizini güncelleyebilirsiniz."
            )
            self.next_step_primary_button.setText("Yeni Aksiyon")
            self.current_next_step_action = "create_action"
            self.current_next_step_secondary_action = "open_ai"
            self.next_step_secondary_button.setText("AI Analizini Aç")
            self.next_step_secondary_button.setVisible(True)

        overview_actions_rows = [
            [
                action.created_at.strftime("%d.%m.%Y"),
                action.contact.name if action.contact else "-",
                action.action_type or "-",
                action.next_action or "-",
            ]
            for action in self.action_items[:5]
        ]
        overview_opportunity_rows = [
            [
                opportunity.title,
                opportunity.stage or "-",
                f"{opportunity.expected_amount:,.2f} {opportunity.currency or ''}".strip(),
                opportunity.expected_close_date.strftime("%d.%m.%Y")
                if opportunity.expected_close_date
                else "-",
            ]
            for opportunity in self.opportunity_items[:5]
        ]
        self._populate_table(
            self.overview_actions_table,
            overview_actions_rows,
            "Henüz aksiyon kaydı yok. Hızlı İşlemler alanından ilk takip aksiyonunu oluşturarak süreci başlatın.",
        )
        self._populate_table(
            self.overview_opportunities_table,
            overview_opportunity_rows,
            "Henüz açık fırsat yok. Ticari potansiyel netleştiğinde yeni fırsat açarak pipeline görünürlüğü sağlayın.",
        )

    def _edit_selected_overview_action(self, _item: QTableWidgetItem | None = None) -> None:
        row = self.overview_actions_table.currentRow()
        action = self.action_items[row] if 0 <= row < min(len(self.action_items), 5) else None
        if not action:
            return
        fresh_action = get_action(action.id)
        if not fresh_action:
            return
        dialog = ActionFormDialog(action=fresh_action, parent=self)
        if dialog.exec():
            update_action(fresh_action.id, dialog.get_data())
            self._after_create("Aksiyon kaydı güncellendi.")

    def _edit_selected_overview_opportunity(self, _item: QTableWidgetItem | None = None) -> None:
        row = self.overview_opportunities_table.currentRow()
        opportunity = (
            self.opportunity_items[row]
            if 0 <= row < min(len(self.opportunity_items), 5)
            else None
        )
        if not opportunity:
            return
        fresh_opportunity = get_opportunity(opportunity.id)
        if not fresh_opportunity:
            return
        dialog = OpportunityFormDialog(opportunity=fresh_opportunity, parent=self)
        if dialog.exec():
            update_opportunity(fresh_opportunity.id, dialog.get_data())
            self._after_create("Fırsat kaydı güncellendi.")

    def _populate_custom_fields_tab(self, custom_rows: list[tuple[FieldDefinition, str]]) -> None:
        while self.custom_fields_grid.count():
            item = self.custom_fields_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not custom_rows:
            empty = QLabel("Görünür özel alan bulunamadı.")
            empty.setObjectName("SectionSubtitle")
            self.custom_fields_grid.addWidget(empty, 0, 0)
            return

        for row, (definition, value) in enumerate(custom_rows):
            title = QLabel(f"{definition.label}:")
            title.setObjectName("SummaryLabel")
            content = QLabel(value)
            content.setObjectName("SummaryValue")
            content.setWordWrap(True)
            content.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.custom_fields_grid.addWidget(title, row, 0)
            self.custom_fields_grid.addWidget(content, row, 1)
        self.custom_fields_grid.setColumnStretch(1, 1)

    def _populate_custom_fields_manager(self) -> None:
        self.manage_fields_table.setRowCount(len(self.custom_field_definitions))
        for row, definition in enumerate(self.custom_field_definitions):
            values = [
                str(definition.sort_order),
                definition.label,
                definition.field_type,
                "Görünür" if definition.is_visible else "Gizli",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.manage_fields_table.setItem(row, column, item)
        self.manage_fields_table.resizeColumnsToContents()

    def _toggle_custom_fields_manage_mode(self, enabled: bool) -> None:
        self.manage_custom_fields_button.setText(
            "Düzenleme Modunu Kapat" if enabled else "Özel Alanları Düzenle"
        )
        self.custom_fields_manage_card.setVisible(enabled)

    def _get_selected_custom_field_definition(self) -> FieldDefinition | None:
        row = self.manage_fields_table.currentRow()
        if row < 0 or row >= len(self.custom_field_definitions):
            return None
        return self.custom_field_definitions[row]

    def _definition_payload(self, definition: FieldDefinition, **overrides: Any) -> dict[str, Any]:
        options_text = ", ".join(parse_options(definition.options_json))
        payload = {
            "entity_type": definition.entity_type,
            "label": definition.label,
            "field_key": definition.field_key,
            "field_type": definition.field_type,
            "is_required": definition.is_required,
            "is_visible": definition.is_visible,
            "sort_order": definition.sort_order,
            "options_text": options_text,
        }
        payload.update(overrides)
        return payload

    def _add_custom_field_definition(self) -> None:
        dialog = FieldDefinitionFormDialog(initial_entity_type="company", parent=self)
        if dialog.exec():
            try:
                create_field_definition(dialog.get_data())
            except ValueError as exc:
                QMessageBox.warning(self, "Bilgi", str(exc))
                return
            self.manage_custom_fields_button.setChecked(True)
            self._after_create("Özel alan tanımı oluşturuldu.")

    def _rename_custom_field_definition(self) -> None:
        definition = self._get_selected_custom_field_definition()
        if not definition:
            QMessageBox.warning(self, "Bilgi", "Lütfen bir alan seçin.")
            return

        new_label, accepted = QInputDialog.getText(
            self,
            "Alanı Yeniden Adlandır",
            "Yeni alan adı:",
            text=definition.label,
        )
        if not accepted or not new_label.strip():
            return

        try:
            update_field_definition(
                definition.id,
                self._definition_payload(definition, label=new_label.strip()),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Bilgi", str(exc))
            return
        self._after_create("Alan adı güncellendi.")

    def _toggle_selected_custom_field_visibility(self) -> None:
        definition = self._get_selected_custom_field_definition()
        if not definition:
            QMessageBox.warning(self, "Bilgi", "Lütfen bir alan seçin.")
            return

        update_field_definition(
            definition.id,
            self._definition_payload(definition, is_visible=not definition.is_visible),
        )
        self._after_create("Alan görünürlüğü güncellendi.")

    def _delete_selected_custom_field_definition(self) -> None:
        definition = self._get_selected_custom_field_definition()
        if not definition:
            QMessageBox.warning(self, "Bilgi", "Lütfen bir alan seçin.")
            return

        answer = QMessageBox.question(
            self,
            "Alan Kaldır",
            f"{definition.label} alanını kaldırmak istiyor musunuz?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            delete_field_definition(definition.id)
            self._after_create("Alan tanımı kaldırıldı.")

    def _move_selected_custom_field_definition(self, direction: str) -> None:
        definition = self._get_selected_custom_field_definition()
        if not definition:
            QMessageBox.warning(self, "Bilgi", "Lütfen bir alan seçin.")
            return

        move_field_definition(definition.id, direction)
        self.refresh_content()
        self.manage_custom_fields_button.setChecked(True)

    def _go_to_field_management_page(self) -> None:
        parent = self.parent()
        main_window = parent.window() if parent else None
        if main_window and hasattr(main_window, "sidebar"):
            main_window.sidebar.setCurrentRow(7)
            self.close()

    def _get_selected_item(self, table: QTableWidget, items: list[Any]) -> Any | None:
        row = table.currentRow()
        if row < 0 or row >= len(items):
            return None
        return items[row]

    def _edit_selected_contact(self, _item: QTableWidgetItem | None = None) -> None:
        contact = self._get_selected_item(self.contacts_table, self.contact_items)
        if not contact:
            QMessageBox.warning(self, "Bilgi", "Lütfen bir kişi seçin.")
            return
        fresh_contact = get_contact(contact.id)
        if not fresh_contact:
            return
        dialog = ContactFormDialog(contact=fresh_contact, parent=self)
        if dialog.exec():
            update_contact(fresh_contact.id, dialog.get_data())
            self._after_create("Kişi kaydı güncellendi.")

    def _edit_selected_action(self, _item: QTableWidgetItem | None = None) -> None:
        action = self._get_selected_item(self.actions_table, self.action_items)
        if not action:
            QMessageBox.warning(self, "Bilgi", "Lütfen bir aksiyon seçin.")
            return
        fresh_action = get_action(action.id)
        if not fresh_action:
            return
        dialog = ActionFormDialog(action=fresh_action, parent=self)
        if dialog.exec():
            update_action(fresh_action.id, dialog.get_data())
            self._after_create("Aksiyon kaydı güncellendi.")

    def _edit_selected_offer(self, _item: QTableWidgetItem | None = None) -> None:
        offer = self._get_selected_item(self.offers_table, self.offer_items)
        if not offer:
            QMessageBox.warning(self, "Bilgi", "Lütfen bir teklif seçin.")
            return
        fresh_offer = get_offer(offer.id)
        if not fresh_offer:
            return
        dialog = OfferFormDialog(offer=fresh_offer, parent=self)
        if dialog.exec():
            previous_status = fresh_offer.status or ""
            update_offer(fresh_offer.id, dialog.get_data())
            self._after_create("Teklif kaydı güncellendi.")
            updated_offer = get_offer(fresh_offer.id)
            if updated_offer:
                self._handle_offer_workflow_suggestions(updated_offer, previous_status)

    def _edit_selected_sample(self, _item: QTableWidgetItem | None = None) -> None:
        sample = self._get_selected_item(self.samples_table, self.sample_items)
        if not sample:
            QMessageBox.warning(self, "Bilgi", "Lütfen bir numune seçin.")
            return
        fresh_sample = get_sample(sample.id)
        if not fresh_sample:
            return
        dialog = SampleFormDialog(sample=fresh_sample, parent=self)
        if dialog.exec():
            previous_status = fresh_sample.status or ""
            update_sample(fresh_sample.id, dialog.get_data())
            self._after_create("Numune kaydı güncellendi.")
            updated_sample = get_sample(fresh_sample.id)
            if updated_sample:
                self._handle_sample_workflow_suggestions(updated_sample, previous_status)

    def _edit_selected_opportunity(self, _item: QTableWidgetItem | None = None) -> None:
        opportunity = self._get_selected_item(self.opportunities_table, self.opportunity_items)
        if not opportunity:
            QMessageBox.warning(self, "Bilgi", "Lütfen bir fırsat seçin.")
            return
        fresh_opportunity = get_opportunity(opportunity.id)
        if not fresh_opportunity:
            return
        dialog = OpportunityFormDialog(opportunity=fresh_opportunity, parent=self)
        if dialog.exec():
            update_opportunity(fresh_opportunity.id, dialog.get_data())
            self._after_create("Fırsat kaydı güncellendi.")

    def _open_contact_form(self) -> None:
        dialog = ContactFormDialog(initial_company_id=self.company_id, parent=self)
        if dialog.exec():
            create_contact(dialog.get_data())
            self._after_create("Kişi kaydı oluşturuldu.")

    def _open_action_form(self) -> None:
        dialog = ActionFormDialog(
            initial_company_id=self.company_id,
            initial_record_type="Sirket",
            parent=self,
        )
        if dialog.exec():
            create_action(dialog.get_data())
            self._after_create("Aksiyon kaydı oluşturuldu.")

    def _open_offer_form(self) -> None:
        dialog = OfferFormDialog(initial_company_id=self.company_id, parent=self)
        if dialog.exec():
            offer = create_offer(dialog.get_data())
            self._after_create("Teklif kaydı oluşturuldu.")
            self._handle_offer_workflow_suggestions(offer, None)

    def _open_sample_form(self) -> None:
        dialog = SampleFormDialog(initial_company_id=self.company_id, parent=self)
        if dialog.exec():
            sample = create_sample(dialog.get_data())
            self._after_create("Numune kaydı oluşturuldu.")
            self._handle_sample_workflow_suggestions(sample, None)

    def _open_opportunity_form(self) -> None:
        dialog = OpportunityFormDialog(initial_company_id=self.company_id, parent=self)
        if dialog.exec():
            create_opportunity(dialog.get_data())
            self._after_create("Fırsat kaydı oluşturuldu.")

    def _after_create(self, message: str) -> None:
        self.refresh_content()
        QMessageBox.information(self, "Bilgi", message)

    def _open_follow_up_action_dialog(self, *, sample: Sample | None = None, offer: Offer | None = None) -> None:
        if sample:
            next_action = "Numune geri bildirimini al"
            summary_note = (
                f"Ürün: {sample.product or '-'}\n"
                f"Durum: {sample.status or '-'}\n"
                f"Adet: {sample.quantity}"
            )
            if sample.note:
                summary_note = f"{summary_note}\nNot: {sample.note}"
            dialog = ActionFormDialog(
                initial_company_id=sample.company_id,
                initial_contact_id=sample.contact_id,
                initial_record_type="Kisi" if sample.contact_id else "Sirket",
                initial_action_type="Numune Takibi",
                initial_channel="Telefon",
                initial_note=summary_note,
                initial_next_action=next_action,
                initial_next_action_date=date.today() + timedelta(days=2),
                parent=self,
            )
        elif offer:
            description, details = split_offer_note(offer.note or "")
            summary_note = (
                f"Teklif No: {offer.offer_no}\n"
                f"Durum: {offer.status or '-'}\n"
                f"Ürün / Açıklama: {description or '-'}"
            )
            if details:
                summary_note = f"{summary_note}\nNot: {details}"
            dialog = ActionFormDialog(
                initial_company_id=offer.company_id,
                initial_contact_id=offer.contact_id,
                initial_record_type="Kisi" if offer.contact_id else "Sirket",
                initial_action_type="Teklif Takibi",
                initial_channel="Telefon",
                initial_note=summary_note,
                initial_next_action="Teklif geri dönüşünü al",
                initial_next_action_date=date.today() + timedelta(days=2),
                parent=self,
            )
        else:
            return

        if dialog.exec():
            create_action(dialog.get_data())
            self._after_create("Takip aksiyonu oluşturuldu.")

    def _handle_offer_workflow_suggestions(self, offer: Offer, previous_status: str | None) -> None:
        current_status = offer.status or ""
        if current_status != "Kabul Edildi" or previous_status == "Kabul Edildi":
            return

        related_opportunity = find_related_open_opportunity(offer.company_id, offer.contact_id)
        if not related_opportunity:
            return

        answer = QMessageBox.question(
            self,
            "Workflow Önerisi",
            (
                f"{offer.offer_no} teklifi kabul edildi. "
                f"İlişkili fırsat \"{related_opportunity.title}\" aşaması \"Kazanıldı\" olarak güncellensin mi?"
            ),
        )
        if answer == QMessageBox.StandardButton.Yes:
            update_opportunity(
                related_opportunity.id,
                {
                    "stage": "Kazanıldı",
                    "probability": 100,
                },
            )
            self._after_create("İlişkili fırsat \"Kazanıldı\" aşamasına güncellendi.")

    def _handle_sample_workflow_suggestions(self, sample: Sample, previous_status: str | None) -> None:
        current_status = sample.status or ""
        if current_status == previous_status:
            return

        if current_status == "Olumlu":
            box = QMessageBox(self)
            box.setWindowTitle("Workflow Önerisi")
            box.setIcon(QMessageBox.Icon.Information)
            box.setText(
                "Numune sonucu olumlu görünüyor. İsterseniz takip aksiyonu oluşturabilir veya yeni fırsat açabilirsiniz."
            )
            action_button = box.addButton("Takip Aksiyonu Oluştur", QMessageBox.ButtonRole.AcceptRole)
            opportunity_button = box.addButton("Fırsat Oluştur", QMessageBox.ButtonRole.ActionRole)
            box.addButton("Daha Sonra", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            clicked = box.clickedButton()
            if clicked == action_button:
                self._open_follow_up_action_dialog(sample=sample)
            elif clicked == opportunity_button:
                title = f"{sample.product} fırsatı" if sample.product else "Yeni fırsat"
                note = "Olumlu numune geri bildirimi alındı."
                if sample.note:
                    note = f"{note}\n{sample.note}"
                dialog = OpportunityFormDialog(
                    initial_company_id=sample.company_id,
                    initial_contact_id=sample.contact_id,
                    initial_title=title,
                    initial_note=note,
                    initial_stage="Numune Gönderildi",
                    parent=self,
                )
                if dialog.exec():
                    create_opportunity(dialog.get_data())
                    self._after_create("Olumlu numuneden yeni fırsat oluşturuldu.")
            return

        if current_status == "Olumsuz":
            answer = QMessageBox.question(
                self,
                "Workflow Önerisi",
                "Numune sonucu olumsuz kaydedildi. Değerlendirme için bir takip aksiyonu oluşturmak ister misiniz?",
            )
            if answer == QMessageBox.StandardButton.Yes:
                self._open_follow_up_action_dialog(sample=sample)


class CompaniesPage(QWidget):
    table_columns = [
        ("name", "Şirket"),
        ("sektor", "Sektör"),
        ("kaynak", "Kaynak"),
        ("potansiyel_urun", "Potansiyel Ürün"),
        ("durum", "Durum"),
        ("next_action", "Sonraki Aksiyon"),
        ("next_action_date", "Takip Tarihi"),
        ("priority", "Öncelik"),
    ]
    export_headers = [
        "ID",
        "Şirket",
        "Ülke",
        "Şehir",
        "Öncelik",
        "Kaynak",
        "Referans Noktası",
        "Sektör",
        "Potansiyel Ürün",
        "Durum",
        "Sonraki Aksiyon",
        "Sonraki Aksiyon Tarihi",
        "Kişi Sayısı",
        "Oluşturma Tarihi",
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.companies: list[Company] = []
        self.company_field_values_map: dict[int, dict[str, str]] = {}

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(12)

        root_layout.addWidget(
            create_page_header(
                "Şirketler",
                "Müşteri adaylarını, öncelikleri ve ilişkili kişileri tek tabloda yönetin.",
            )
        )

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Şirket, şehir veya ülkeye göre ara...")
        self.search_input.textChanged.connect(self.refresh_table)

        self.priority_filter = QComboBox()
        self.priority_filter.setMinimumWidth(92)
        self.priority_filter.addItem("Tumu", None)
        for priority in range(1, 6):
            self.priority_filter.addItem(f"★ {priority}", priority)
        self.priority_filter.currentIndexChanged.connect(self.refresh_table)

        self.bulk_count_label, self.bulk_button = create_bulk_action_controls()
        self.bulk_menu = QMenu(self.bulk_button)
        self.bulk_menu.addAction("Toplu Öncelik Değiştir", self.bulk_update_priority)
        self.bulk_menu.addAction("Toplu Durum Güncelle", self.bulk_update_status)
        self.bulk_menu.addAction("Toplu Kaynak Güncelle", self.bulk_update_source)
        self.bulk_menu.addAction("Toplu Takip Tarihi Ata", self.bulk_assign_follow_up_date)
        self.bulk_button.setMenu(self.bulk_menu)

        add_button = QPushButton("Yeni Şirket")
        quick_action_button = QPushButton("Hızlı Aksiyon")
        quick_offer_button = QPushButton("Hızlı Teklif")
        views_button = QPushButton("Görünümler")
        columns_button = QPushButton("Kolonlar")
        edit_button = QPushButton("Düzenle")
        delete_button = QPushButton("Sil")
        import_button = QPushButton("İçe Aktar")
        export_button = QPushButton("Dışa Aktar")
        set_button_role(add_button, "primary")
        set_button_role(quick_action_button, "secondary")
        set_button_role(quick_offer_button, "ghost")
        set_button_role(views_button, "ghost")
        set_button_role(columns_button, "ghost")
        set_button_role(edit_button, "secondary")
        set_button_role(delete_button, "danger")
        set_button_role(import_button, "ghost")
        set_button_role(export_button, "ghost")

        add_button.clicked.connect(self.add_company)
        quick_action_button.clicked.connect(self.quick_create_action)
        quick_offer_button.clicked.connect(self.quick_create_offer)
        edit_button.clicked.connect(self.edit_selected_company)
        delete_button.clicked.connect(self.delete_selected_company)
        import_button.clicked.connect(self.import_companies_file)
        export_button.clicked.connect(self.export_companies_file)

        toolbar_card = create_list_page_toolbar(
            "Şirket Listesi",
            "Arama, filtreleme ve temel kayıt işlemleri",
            top_actions=[
                add_button,
                quick_action_button,
                quick_offer_button,
                self.bulk_count_label,
                self.bulk_button,
                views_button,
                columns_button,
                edit_button,
                delete_button,
                import_button,
                export_button,
            ],
            search_widget=self.search_input,
            filter_widgets=[self.priority_filter],
        )

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.table_columns))
        self.table.setHorizontalHeaderLabels([header for _key, header in self.table_columns])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemDoubleClicked.connect(self.show_company_detail)
        configure_table(self.table)
        self.table.itemSelectionChanged.connect(self._update_bulk_actions_state)
        self.preferences = ListPagePreferences(
            "companies",
            self.table,
            filter_widgets={
                "search": self.search_input,
                "priority": self.priority_filter,
            },
            default_visible_columns=list(range(len(self.table_columns))),
            reset_callback=self.refresh_table,
        )
        self.preferences.attach_button(columns_button)
        self.preferences.attach_view_button(
            views_button,
            built_in_views={
                "Yüksek Öncelik": {
                    "filters": {
                        "search": {"kind": "line_edit", "text": ""},
                        "priority": {"kind": "combo_box", "data": 5, "text": "★ 5"},
                    }
                }
            },
        )

        table_card = create_list_table_card(self.table)

        root_layout.addWidget(toolbar_card)
        root_layout.addWidget(table_card, 1)

        self.preferences.restore()
        self.refresh_table()

    def refresh_table(self) -> None:
        priority = self.priority_filter.currentData()
        self.companies = list_companies(self.search_input.text().strip(), priority)
        ensure_company_business_fields()
        self.company_field_values_map = get_field_values_map(
            "company",
            [company.id for company in self.companies],
        )
        self.table.setRowCount(len(self.companies))

        if not self.companies:
            set_table_empty_state(
                self.table,
                "Arama ve filtrelere uygun şirket kaydı bulunamadı.",
                action_label="Yeni Şirket",
                action_handler=self.add_company,
            )
            self.preferences.finalize_table_state()
            self._update_bulk_actions_state()
            return

        name_font = QFont("Segoe UI", 10)
        name_font.setBold(True)
        for row, company in enumerate(self.companies):
            values = self._get_company_table_values(company)
            for column, value in enumerate(values):
                key = self.table_columns[column][0]
                if key == "priority":
                    set_priority_table_cell(self.table, row, column, company.priority)
                    continue

                item = QTableWidgetItem(value)
                if key == "name":
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                    )
                    item.setFont(name_font)
                    item.setForeground(QColor("#12243a"))
                elif key in {"next_action", "potansiyel_urun"}:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                    )
                    item.setForeground(QColor("#44566d"))
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if key in {"kaynak", "durum", "next_action_date"}:
                        item.setForeground(QColor("#61748c"))
                if column == 0:
                    set_row_identifier(item, company.id)
                self.table.setItem(row, column, item)

        self.table.resizeColumnsToContents()
        self.preferences.finalize_table_state()
        self._update_bulk_actions_state()

    def _get_company_table_values(self, company: Company) -> list[str]:
        field_values = self.company_field_values_map.get(company.id, {})
        next_action, next_action_date = self._get_company_follow_up(company)
        row_map = {
            "name": company.name,
            "sektor": field_values.get("sektor") or "-",
            "kaynak": field_values.get("kaynak") or "-",
            "potansiyel_urun": field_values.get("potansiyel_urun") or "-",
            "durum": field_values.get("durum") or "-",
            "next_action": next_action,
            "next_action_date": next_action_date,
            "priority": "",
        }
        return [row_map[key] for key, _header in self.table_columns]

    def _get_company_follow_up(self, company: Company) -> tuple[str, str]:
        if not company.actions:
            return "-", "-"

        dated_actions = sorted(
            [action for action in company.actions if action.next_action_date],
            key=lambda action: (action.next_action_date, action.created_at),
            reverse=True,
        )
        target_action = dated_actions[0] if dated_actions else max(
            company.actions,
            key=lambda action: action.created_at,
        )
        return (
            target_action.next_action or "-",
            target_action.next_action_date.strftime("%d.%m.%Y")
            if target_action.next_action_date
            else "-",
        )

    def _get_follow_up_target_action(self, company: Company):
        if not company.actions:
            return None
        dated_actions = sorted(
            [action for action in company.actions if action.next_action_date],
            key=lambda action: (action.next_action_date, action.created_at),
            reverse=True,
        )
        return dated_actions[0] if dated_actions else max(company.actions, key=lambda action: action.created_at)

    def add_company(self) -> None:
        dialog = CompanyDialog(parent=self)
        if dialog.exec():
            create_company(dialog.get_data())
            self.refresh_table()
            self._notify("Şirket kaydı oluşturuldu.")

    def export_companies_file(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Şirketleri Dışa Aktar",
            get_default_export_path("sirketler.csv"),
            "CSV Dosyaları (*.csv);;Excel Dosyaları (*.xlsx)",
        )
        if not file_path:
            return

        rows = [
            [
                company.id,
                company.name,
                company.country,
                company.city,
                company.priority,
                self.company_field_values_map.get(company.id, {}).get("kaynak") or "-",
                self.company_field_values_map.get(company.id, {}).get("referans_noktasi") or "-",
                self.company_field_values_map.get(company.id, {}).get("sektor") or "-",
                self.company_field_values_map.get(company.id, {}).get("potansiyel_urun") or "-",
                self.company_field_values_map.get(company.id, {}).get("durum") or "-",
                self._get_company_follow_up(company)[0],
                self._get_company_follow_up(company)[1],
                len(company.contacts),
                company.created_at.strftime("%d.%m.%Y"),
            ]
            for company in self.companies
        ]
        export_rows(file_path, self.export_headers, rows)
        self._notify("Şirket listesi dışa aktarıldı.")

    def import_companies_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Şirketleri İçe Aktar",
            get_default_import_dir(),
            "Desteklenen Dosyalar (*.csv *.xlsx)",
        )
        if not file_path:
            return

        summary = import_companies(file_path)
        self.refresh_table()
        self._show_import_summary("Şirket İçe Aktar", summary.added, summary.updated, summary.skipped, summary.errors)

    def edit_selected_company(self) -> None:
        company = self._get_selected_company()
        if not company:
            self._notify("Lütfen bir şirket seçin.", error=True)
            return

        dialog = CompanyDialog(company=company, parent=self)
        if dialog.exec():
            update_company(company.id, dialog.get_data())
            self.refresh_table()
            self._notify("Şirket kaydı güncellendi.")

    def delete_selected_company(self) -> None:
        company = self._get_selected_company()
        if not company:
            self._notify("Lütfen bir şirket seçin.", error=True)
            return

        answer = QMessageBox.question(
            self,
            "Şirket Sil",
            f"{company.name} kaydını silmek istiyor musunuz?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            delete_company(company.id)
            self.refresh_table()
            self._notify("Şirket kaydı silindi.")

    def show_company_detail(self, _item: QTableWidgetItem | None = None) -> None:
        company = self._get_selected_company()
        if not company:
            return

        fresh_company = get_company(company.id)
        if not fresh_company:
            return

        dialog = CompanyDetailDialog(fresh_company, self)
        dialog.exec()

    def quick_create_action(self) -> None:
        company = self._get_selected_company()
        if not company:
            self._notify("Lütfen önce bir şirket seçin.", error=True)
            return

        dialog = ActionFormDialog(
            initial_company_id=company.id,
            initial_action_type="Arama",
            initial_channel="Telefon",
            initial_next_action="İlk teması kur",
            parent=self,
        )
        if dialog.exec():
            create_action(dialog.get_data())
            self.refresh_table()
            self._notify("Şirket için hızlı aksiyon oluşturuldu.")

    def quick_create_offer(self) -> None:
        company = self._get_selected_company()
        if not company:
            self._notify("Lütfen önce bir şirket seçin.", error=True)
            return

        dialog = OfferFormDialog(initial_company_id=company.id, parent=self)
        if dialog.exec():
            create_offer(dialog.get_data())
            self._notify("Şirket için hızlı teklif oluşturuldu.")

    def _get_selected_company(self) -> Company | None:
        selected_ids = get_selected_row_identifiers(self.table)
        if len(selected_ids) != 1:
            return None
        company_id = selected_ids[0]
        if company_id is None:
            return None
        return next((company for company in self.companies if company.id == company_id), None)

    def _get_selected_companies(self) -> list[Company]:
        selected_ids = get_selected_row_identifiers(self.table)
        selected_map = {company.id: company for company in self.companies}
        return [selected_map[company_id] for company_id in selected_ids if company_id in selected_map]

    def _update_bulk_actions_state(self) -> None:
        update_bulk_action_controls(self.bulk_count_label, self.bulk_button, len(self._get_selected_companies()))

    def _apply_bulk_company_action(self, action_label: str, callback) -> None:
        companies = self._get_selected_companies()
        if len(companies) < 2:
            self._notify("Toplu işlem için en az iki şirket seçin.", error=True)
            return
        if not confirm_bulk_action(self, action_label, len(companies)):
            return

        success_count = 0
        skipped_count = 0
        failures: list[str] = []
        for company in companies:
            try:
                result = callback(company)
                if result is False:
                    skipped_count += 1
                else:
                    success_count += 1
            except Exception as exc:
                failures.append(f"{company.name}: {exc}")

        self.refresh_table()
        show_bulk_result(
            self,
            success_count=success_count,
            skipped_count=skipped_count,
            failures=failures,
        )

    def _get_company_field_options(self, field_key: str) -> list[str]:
        for config in COMPANY_PROSPECTING_FIELDS:
            if config["field_key"] == field_key:
                return parse_options(config.get("options_text", ""))
        return []

    def bulk_update_priority(self) -> None:
        priority_value, accepted = QInputDialog.getInt(
            self,
            "Toplu Öncelik Değiştir",
            "Yeni öncelik:",
            value=3,
            minValue=1,
            maxValue=5,
        )
        if not accepted:
            return

        self._apply_bulk_company_action(
            "Toplu Öncelik Değiştir",
            lambda company: update_company(
                company.id,
                {
                    "priority": priority_value,
                    "custom_values": dict(self.company_field_values_map.get(company.id, {})),
                },
            ),
        )

    def bulk_update_status(self) -> None:
        options = self._get_company_field_options("durum")
        if not options:
            self._notify("Durum seçenekleri bulunamadı.", error=True)
            return
        value, accepted = QInputDialog.getItem(
            self,
            "Toplu Durum Güncelle",
            "Yeni durum:",
            options,
            0,
            False,
        )
        if not accepted or not value:
            return
        self._apply_bulk_company_action(
            "Toplu Durum Güncelle",
            lambda company: save_field_values(
                "company",
                company.id,
                {**self.company_field_values_map.get(company.id, {}), "durum": value},
            ),
        )

    def bulk_update_source(self) -> None:
        options = self._get_company_field_options("kaynak")
        if not options:
            self._notify("Kaynak seçenekleri bulunamadı.", error=True)
            return
        value, accepted = QInputDialog.getItem(
            self,
            "Toplu Kaynak Güncelle",
            "Yeni kaynak:",
            options,
            0,
            False,
        )
        if not accepted or not value:
            return
        self._apply_bulk_company_action(
            "Toplu Kaynak Güncelle",
            lambda company: save_field_values(
                "company",
                company.id,
                {**self.company_field_values_map.get(company.id, {}), "kaynak": value},
            ),
        )

    def bulk_assign_follow_up_date(self) -> None:
        dialog = BulkDateDialog("Toplu Takip Tarihi Ata", "Takip tarihi:", self)
        if not dialog.exec():
            return
        target_date = dialog.get_value()

        def assign_date(company: Company) -> bool:
            action = self._get_follow_up_target_action(company)
            if not action:
                return False
            update_action(action.id, {"next_action_date": target_date})
            return True

        self._apply_bulk_company_action("Toplu Takip Tarihi Ata", assign_date)

    def _notify(self, message: str, error: bool = False) -> None:
        box = QMessageBox.warning if error else QMessageBox.information
        box(self, "Bilgi", message)

    def _show_import_summary(
        self,
        title: str,
        added: int,
        updated: int,
        skipped: int,
        errors: list[str],
    ) -> None:
        lines = [
            f"Eklenen: {added}",
            f"Güncellenen: {updated}",
            f"Atlanan: {skipped}",
            f"Hata: {len(errors)}",
        ]
        if errors:
            lines.append("")
            lines.extend(errors[:8])
        QMessageBox.information(self, title, "\n".join(lines))
