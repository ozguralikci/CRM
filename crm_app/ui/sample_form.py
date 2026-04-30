from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
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

from crm_app.models import Sample
from crm_app.services.contact_service import list_company_choices, list_contact_choices
from crm_app.services.sample_service import list_sample_statuses
from crm_app.ui.layout_helpers import create_scroll_area
from crm_app.ui.styles import apply_shadow, create_content_card, style_dialog_buttons


class SampleFormDialog(QDialog):
    def __init__(
        self,
        sample: Sample | None = None,
        initial_company_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Numune")
        self.setMinimumSize(700, 720)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header_card = QFrame()
        header_card.setObjectName("DialogCard")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(6)
        apply_shadow(header_card, blur=14, y_offset=2, alpha=10)

        title = QLabel("Numune Bilgileri")
        title.setObjectName("DialogTitle")
        subtitle = QLabel("Numune gönderimlerini, durumlarını ve geri dönüş sürecini yönetin.")
        subtitle.setObjectName("DialogSubtitle")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        scroll_area, _scroll_content, scroll_layout = create_scroll_area(max_content_width=880)

        self.company_input = QComboBox()
        self.contact_input = QComboBox()
        self.product_input = QLineEdit(sample.product if sample else "")
        self.quantity_input = QSpinBox()
        self.quantity_input.setRange(0, 100000)
        self.quantity_input.setValue(sample.quantity if sample else 1)

        self.sent_date_input = QDateEdit()
        self.sent_date_input.setCalendarPopup(True)
        self.sent_date_input.setDate(QDate.currentDate())

        self.status_input = QComboBox()
        self.note_input = QTextEdit(sample.note if sample else "")
        self.note_input.setMinimumHeight(150)

        selected_company_id = sample.company_id if sample else initial_company_id
        self._load_companies(selected_company_id=selected_company_id)
        self._load_contacts(
            selected_company_id=sample.company_id if sample else self.company_input.currentData(),
            selected_contact_id=sample.contact_id if sample else None,
        )
        self._load_statuses()

        if sample:
            if sample.sent_date:
                self.sent_date_input.setDate(
                    QDate(sample.sent_date.year, sample.sent_date.month, sample.sent_date.day)
                )
            self.status_input.setCurrentText(sample.status or "Hazırlanıyor")

        basic_form = QFormLayout()
        basic_form.setHorizontalSpacing(18)
        basic_form.setVerticalSpacing(12)
        basic_form.addRow("Şirket", self.company_input)
        basic_form.addRow("Kişi", self.contact_input)
        basic_form.addRow("Ürün", self.product_input)
        basic_form.addRow("Adet", self.quantity_input)
        scroll_layout.addWidget(
            self._create_form_section(
                "Temel Bilgiler",
                "Numunenin bağlı olduğu şirketi, kişiyi ve ürün bilgisini tanımlayın.",
                basic_form,
            )
        )

        shipping_form = QFormLayout()
        shipping_form.setHorizontalSpacing(18)
        shipping_form.setVerticalSpacing(12)
        shipping_form.addRow("Gönderim Tarihi", self.sent_date_input)
        shipping_form.addRow("Durum", self.status_input)
        scroll_layout.addWidget(
            self._create_form_section(
                "Gönderim Bilgileri",
                "Numune gönderim zamanını ve mevcut durumunu takip edin.",
                shipping_form,
            )
        )

        note_card = create_content_card()
        note_layout = QVBoxLayout(note_card)
        note_layout.setContentsMargins(16, 16, 16, 16)
        note_layout.setSpacing(10)
        note_title = QLabel("Notlar")
        note_title.setObjectName("SectionTitle")
        note_subtitle = QLabel("Geri bildirim, lojistik detaylar veya müşteri notlarını buraya ekleyin.")
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

    def _load_statuses(self) -> None:
        self.status_input.clear()
        for status in list_sample_statuses():
            self.status_input.addItem(status)

    def _on_company_changed(self) -> None:
        self._load_contacts(selected_company_id=self.company_input.currentData())

    def get_data(self) -> dict[str, object]:
        return {
            "company_id": self.company_input.currentData(),
            "contact_id": self.contact_input.currentData(),
            "product": self.product_input.text().strip(),
            "quantity": self.quantity_input.value(),
            "sent_date": self.sent_date_input.date().toPython(),
            "status": self.status_input.currentText().strip(),
            "note": self.note_input.toPlainText().strip(),
        }

    def accept(self) -> None:
        if self.company_input.count() == 0 or self.company_input.currentData() is None:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen bir şirket seçin.")
            return

        if not self.product_input.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Ürün bilgisi zorunludur.")
            return

        super().accept()
