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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from crm_app.models import Offer
from crm_app.services.contact_service import list_company_choices, list_contact_choices
from crm_app.services.offer_service import (
    generate_offer_no,
    list_offer_currencies,
    list_offer_statuses,
    merge_offer_note,
    split_offer_note,
)
from crm_app.ui.layout_helpers import create_scroll_area
from crm_app.ui.styles import apply_shadow, create_content_card, style_dialog_buttons


class OfferFormDialog(QDialog):
    def __init__(
        self,
        offer: Offer | None = None,
        initial_company_id: int | None = None,
        initial_contact_id: int | None = None,
        initial_description: str = "",
        initial_amount: float | None = None,
        initial_currency: str = "",
        initial_note: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Teklif")
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

        title = QLabel("Teklif Bilgileri")
        title.setObjectName("DialogTitle")
        subtitle = QLabel("Teklifleri, durumlarını ve bağlı kişi bilgisini yönetin.")
        subtitle.setObjectName("DialogSubtitle")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        scroll_area, _scroll_content, scroll_layout = create_scroll_area(max_content_width=900)

        self.offer_no_input = QLineEdit(offer.offer_no if offer else generate_offer_no())
        self.company_input = QComboBox()
        self.contact_input = QComboBox()

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())

        self.description_input = QTextEdit()
        self.description_input.setMinimumHeight(120)
        self.amount_input = QDoubleSpinBox()
        self.amount_input.setRange(0, 999999999.99)
        self.amount_input.setDecimals(2)
        self.amount_input.setValue(0.0)

        self.currency_input = QComboBox()
        self.status_input = QComboBox()
        self.file_path_input = QLineEdit()
        self.note_input = QTextEdit()
        self.note_input.setMinimumHeight(140)

        selected_company_id = offer.company_id if offer else initial_company_id
        self._load_companies(selected_company_id=selected_company_id)
        self._load_contacts(
            selected_company_id=offer.company_id if offer else self.company_input.currentData(),
            selected_contact_id=offer.contact_id if offer else initial_contact_id,
        )
        self._load_currencies()
        self._load_statuses()

        if offer:
            description, details = split_offer_note(offer.note or "")
            if offer.date:
                self.date_input.setDate(QDate(offer.date.year, offer.date.month, offer.date.day))
            self.description_input.setPlainText(description)
            self.amount_input.setValue(float(offer.amount or 0))
            self.currency_input.setCurrentText(offer.currency or "EUR")
            self.status_input.setCurrentText(offer.status or "Hazırlanıyor")
            self.file_path_input.setText(offer.file_path or "")
            self.note_input.setPlainText(details)
        else:
            self.description_input.setPlainText(initial_description)
            if initial_amount is not None:
                self.amount_input.setValue(float(initial_amount))
            if initial_currency:
                self.currency_input.setCurrentText(initial_currency)
            if initial_note:
                self.note_input.setPlainText(initial_note)

        basic_form = QFormLayout()
        basic_form.setHorizontalSpacing(18)
        basic_form.setVerticalSpacing(12)
        basic_form.addRow("Teklif No", self.offer_no_input)
        basic_form.addRow("Şirket", self.company_input)
        basic_form.addRow("Kişi", self.contact_input)
        basic_form.addRow("Tarih", self.date_input)
        scroll_layout.addWidget(
            self._create_form_section(
                "Temel Bilgiler",
                "Teklifin bağlı olduğu şirketi, kişiyi ve teklif tarihini belirleyin.",
                basic_form,
            )
        )

        content_form = QFormLayout()
        content_form.setHorizontalSpacing(18)
        content_form.setVerticalSpacing(12)
        content_form.addRow("Ürün / Açıklama", self.description_input)
        content_form.addRow("Tutar", self.amount_input)
        content_form.addRow("Para Birimi", self.currency_input)
        content_form.addRow("Durum", self.status_input)
        scroll_layout.addWidget(
            self._create_form_section(
                "Teklif İçeriği",
                "Teklif kapsamını, fiyat bilgisini ve güncel durumunu kaydedin.",
                content_form,
            )
        )

        notes_form = QFormLayout()
        notes_form.setHorizontalSpacing(18)
        notes_form.setVerticalSpacing(12)
        notes_form.addRow("Dosya Yolu", self.file_path_input)
        notes_form.addRow("Not", self.note_input)
        scroll_layout.addWidget(
            self._create_form_section(
                "Dosya ve Notlar",
                "Teklif dosya yolunu ve paylaşılacak ek açıklamaları not edin.",
                notes_form,
            )
        )

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

    def _load_currencies(self) -> None:
        self.currency_input.clear()
        for currency in list_offer_currencies():
            self.currency_input.addItem(currency)

    def _load_statuses(self) -> None:
        self.status_input.clear()
        for status in list_offer_statuses():
            self.status_input.addItem(status)

    def _on_company_changed(self) -> None:
        self._load_contacts(selected_company_id=self.company_input.currentData())

    def get_data(self) -> dict[str, object]:
        description = self.description_input.toPlainText().strip()
        notes = self.note_input.toPlainText().strip()

        return {
            "offer_no": self.offer_no_input.text().strip(),
            "company_id": self.company_input.currentData(),
            "contact_id": self.contact_input.currentData(),
            "date": self.date_input.date().toPython(),
            "amount": self.amount_input.value(),
            "currency": self.currency_input.currentText().strip(),
            "status": self.status_input.currentText().strip(),
            "file_path": self.file_path_input.text().strip(),
            "note": merge_offer_note(description, notes),
        }

    def accept(self) -> None:
        if self.company_input.count() == 0 or self.company_input.currentData() is None:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen bir şirket seçin.")
            return

        if not self.offer_no_input.text().strip():
            self.offer_no_input.setText(generate_offer_no())

        super().accept()
