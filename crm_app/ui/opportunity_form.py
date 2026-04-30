from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from crm_app.models import Opportunity
from crm_app.services.contact_service import list_company_choices, list_contact_choices
from crm_app.services.opportunity_service import (
    list_opportunity_currencies,
    list_opportunity_stages,
)
from crm_app.ui.layout_helpers import create_scroll_area
from crm_app.ui.styles import apply_shadow, create_content_card, style_dialog_buttons


class OpportunityFormDialog(QDialog):
    def __init__(
        self,
        opportunity: Opportunity | None = None,
        initial_company_id: int | None = None,
        initial_contact_id: int | None = None,
        initial_title: str = "",
        initial_note: str = "",
        initial_stage: str = "",
        initial_amount: float | None = None,
        initial_currency: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Fırsat")
        self.setMinimumSize(720, 760)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header_card = QFrame()
        header_card.setObjectName("DialogCard")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(6)
        apply_shadow(header_card, blur=14, y_offset=2, alpha=10)

        title = QLabel("Fırsat Bilgileri")
        title.setObjectName("DialogTitle")
        subtitle = QLabel("Satış sürecindeki fırsatları aşama bazlı takip edin.")
        subtitle.setObjectName("DialogSubtitle")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        scroll_area, _scroll_content, scroll_layout = create_scroll_area(max_content_width=900)

        self.title_input = QLineEdit(opportunity.title if opportunity else initial_title)
        self.company_input = QComboBox()
        self.contact_input = QComboBox()
        self.stage_input = QComboBox()
        self.expected_amount_input = QDoubleSpinBox()
        self.expected_amount_input.setRange(0, 999999999.99)
        self.expected_amount_input.setDecimals(2)
        self.expected_amount_input.setValue(
            float(opportunity.expected_amount)
            if opportunity
            else float(initial_amount or 0.0)
        )
        self.currency_input = QComboBox()
        self.probability_input = QSpinBox()
        self.probability_input.setRange(0, 100)
        self.probability_input.setSuffix(" %")
        self.probability_input.setValue(opportunity.probability if opportunity else 0)
        self.expected_close_date_input = QDateEdit()
        self.expected_close_date_input.setCalendarPopup(True)
        self.expected_close_date_input.setDate(QDate.currentDate())
        self.note_input = QTextEdit(opportunity.note if opportunity else initial_note)
        self.note_input.setMinimumHeight(150)

        selected_company_id = opportunity.company_id if opportunity else initial_company_id
        self._load_companies(selected_company_id=selected_company_id)
        self._load_contacts(
            selected_company_id=opportunity.company_id if opportunity else self.company_input.currentData(),
            selected_contact_id=opportunity.contact_id if opportunity else initial_contact_id,
        )
        self._load_stages()
        self._load_currencies()

        if opportunity:
            self.stage_input.setCurrentText(opportunity.stage)
            self.currency_input.setCurrentText(opportunity.currency or "EUR")
            if opportunity.expected_close_date:
                self.expected_close_date_input.setDate(
                    QDate(
                        opportunity.expected_close_date.year,
                        opportunity.expected_close_date.month,
                        opportunity.expected_close_date.day,
                    )
                )
        else:
            if initial_stage:
                self.stage_input.setCurrentText(initial_stage)
            if initial_currency:
                self.currency_input.setCurrentText(initial_currency)

        basic_form = QFormLayout()
        basic_form.setHorizontalSpacing(18)
        basic_form.setVerticalSpacing(12)
        basic_form.addRow("Fırsat", self.title_input)
        basic_form.addRow("Şirket", self.company_input)
        basic_form.addRow("Kişi", self.contact_input)
        scroll_layout.addWidget(
            self._create_form_section(
                "Temel Bilgiler",
                "Fırsat başlığını, bağlı şirketi ve ilgili kişiyi tanımlayın.",
                basic_form,
            )
        )

        commercial_form = QFormLayout()
        commercial_form.setHorizontalSpacing(18)
        commercial_form.setVerticalSpacing(12)
        commercial_form.addRow("Aşama", self.stage_input)
        commercial_form.addRow("Beklenen Tutar", self.expected_amount_input)
        commercial_form.addRow("Para Birimi", self.currency_input)
        commercial_form.addRow("Olasılık", self.probability_input)
        commercial_form.addRow("Tahmini Kapanış", self.expected_close_date_input)
        scroll_layout.addWidget(
            self._create_form_section(
                "Ticari Bilgiler",
                "Pipeline aşamasını, finansal beklentiyi ve kapanış olasılığını takip edin.",
                commercial_form,
            )
        )

        note_card = create_content_card()
        note_layout = QVBoxLayout(note_card)
        note_layout.setContentsMargins(16, 16, 16, 16)
        note_layout.setSpacing(10)
        note_title = QLabel("Notlar")
        note_title.setObjectName("SectionTitle")
        note_subtitle = QLabel("Stratejik notlar, rekabet durumu veya müşteri bağlamını kaydedin.")
        note_subtitle.setObjectName("SectionSubtitle")
        note_subtitle.setWordWrap(True)
        note_layout.addWidget(note_title)
        note_layout.addWidget(note_subtitle)
        note_layout.addWidget(self.note_input)
        scroll_layout.addWidget(note_card)

        scroll_layout.addStretch()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        style_dialog_buttons(buttons)

        self.company_input.currentIndexChanged.connect(self._on_company_changed)

        footer_card = QFrame()
        footer_card.setObjectName("DialogCard")
        footer_layout = QHBoxLayout(footer_card)
        footer_layout.setContentsMargins(16, 12, 16, 12)
        footer_layout.addStretch()
        footer_layout.addWidget(buttons)

        layout.addWidget(header_card)
        layout.addWidget(scroll_area, 1)
        layout.addWidget(footer_card)

    def _create_form_section(self, title: str, subtitle: str, content: object) -> QFrame:
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

    def _load_companies(self, selected_company_id: int | None = None) -> None:
        self.company_input.clear()
        for company in list_company_choices():
            self.company_input.addItem(company.name, company.id)

        if selected_company_id is not None:
            index = self.company_input.findData(selected_company_id)
            if index >= 0:
                self.company_input.setCurrentIndex(index)

    def _load_contacts(
        self,
        selected_company_id: int | None = None,
        selected_contact_id: int | None = None,
    ) -> None:
        self.contact_input.clear()
        self.contact_input.addItem("Seçilmedi", None)
        for contact in list_contact_choices(selected_company_id):
            self.contact_input.addItem(contact.name, contact.id)

        if selected_contact_id is not None:
            index = self.contact_input.findData(selected_contact_id)
            if index >= 0:
                self.contact_input.setCurrentIndex(index)

    def _load_stages(self) -> None:
        self.stage_input.clear()
        for stage in list_opportunity_stages():
            self.stage_input.addItem(stage)

    def _load_currencies(self) -> None:
        self.currency_input.clear()
        for currency in list_opportunity_currencies():
            self.currency_input.addItem(currency)

    def _on_company_changed(self) -> None:
        self._load_contacts(selected_company_id=self.company_input.currentData())

    def get_data(self) -> dict[str, object]:
        return {
            "title": self.title_input.text().strip(),
            "company_id": self.company_input.currentData(),
            "contact_id": self.contact_input.currentData(),
            "stage": self.stage_input.currentText().strip(),
            "expected_amount": self.expected_amount_input.value(),
            "currency": self.currency_input.currentText().strip(),
            "probability": self.probability_input.value(),
            "expected_close_date": self.expected_close_date_input.date().toPython(),
            "note": self.note_input.toPlainText().strip(),
        }

    def accept(self) -> None:
        if not self.title_input.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Fırsat adı zorunludur.")
            return

        if self.company_input.count() == 0 or self.company_input.currentData() is None:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen bir şirket seçin.")
            return

        super().accept()
