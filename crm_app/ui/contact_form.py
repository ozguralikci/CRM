from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QSizePolicy,
)

from crm_app.models import Contact
from crm_app.services.contact_service import list_company_choices
from crm_app.ui.dynamic_fields import DynamicFieldsSection
from crm_app.ui.layout_helpers import create_scroll_area
from crm_app.ui.styles import apply_shadow, create_content_card, style_dialog_buttons


class ContactFormDialog(QDialog):
    LABEL_WIDTH = 148

    def __init__(
        self,
        contact: Contact | None = None,
        initial_company_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Kişi")
        self.setMinimumSize(760, 700)
        self.contact = contact

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header_card = QFrame()
        header_card.setObjectName("DialogCard")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(6)
        apply_shadow(header_card, blur=14, y_offset=2, alpha=10)

        title = QLabel("Kişi Bilgileri")
        title.setObjectName("DialogTitle")
        subtitle = QLabel("Şirket bağlantılı kişi kayıtlarını düzenleyin.")
        subtitle.setObjectName("DialogSubtitle")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        scroll_area, _scroll_content, scroll_layout = create_scroll_area(spacing=14)

        self.name_input = QLineEdit(contact.name if contact else "")
        self.company_input = QComboBox()
        self.title_input = QLineEdit(contact.title if contact else "")
        self.email_input = QLineEdit(contact.email if contact else "")
        self.phone_input = QLineEdit(contact.phone if contact else "")
        self.linkedin_input = QLineEdit(contact.linkedin if contact else "")
        for widget in (
            self.name_input,
            self.company_input,
            self.title_input,
            self.email_input,
            self.phone_input,
            self.linkedin_input,
        ):
            self._configure_input_widget(widget)

        selected_company_id = contact.company_id if contact else initial_company_id
        self._load_companies(selected_company_id=selected_company_id)

        self.dynamic_fields = DynamicFieldsSection(
            "contact",
            entity_id=contact.id if contact else None,
            show_header=False,
            parent=self,
        )
        self.dynamic_sections = [self.dynamic_fields] if self.dynamic_fields.has_fields() else []

        basic_form = QFormLayout()
        self._configure_form_layout(basic_form)
        self._add_form_row(basic_form, "Ad Soyad", self.name_input)
        self._add_form_row(basic_form, "Şirket", self.company_input)
        self._add_form_row(basic_form, "Ünvan", self.title_input)
        scroll_layout.addWidget(
            self._create_form_section(
                "Temel Bilgiler",
                "Kişinin temel kimlik ve şirket bağlantı bilgisini girin.",
                basic_form,
            )
        )

        contact_form = QFormLayout()
        self._configure_form_layout(contact_form)
        self._add_form_row(contact_form, "E-posta", self.email_input)
        self._add_form_row(contact_form, "Telefon", self.phone_input)
        self._add_form_row(contact_form, "LinkedIn", self.linkedin_input)
        scroll_layout.addWidget(
            self._create_form_section(
                "İletişim Bilgileri",
                "Kişiye ulaşmak için kullanılacak iletişim kanallarını ekleyin.",
                contact_form,
            )
        )

        if self.dynamic_fields.has_fields():
            scroll_layout.addWidget(
                self._create_form_section(
                    "Ek Alanlar",
                    "Alan Yönetimi ekranından gelen kişi alanlarını burada tamamlayın.",
                    self.dynamic_fields,
                )
            )

        scroll_layout.addStretch()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        style_dialog_buttons(buttons)

        footer_card = QFrame()
        footer_card.setObjectName("DialogCard")
        footer_layout = QHBoxLayout(footer_card)
        footer_layout.setContentsMargins(16, 14, 16, 12)
        footer_layout.addStretch()
        footer_layout.addWidget(buttons)
        footer_card.setStyleSheet("border-top: 1px solid #e7edf4;")

        layout.addWidget(header_card)
        layout.addWidget(scroll_area, 1)
        layout.addWidget(footer_card)

    def _create_form_section(self, title: str, subtitle: str, content: object) -> QFrame:
        card = create_content_card()
        section_layout = QVBoxLayout(card)
        section_layout.setContentsMargins(20, 18, 20, 18)
        section_layout.setSpacing(12)

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

    def _configure_form_layout(self, form: QFormLayout) -> None:
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.setHorizontalSpacing(20)
        form.setVerticalSpacing(14)

    def _add_form_row(self, form: QFormLayout, label_text: str, field: QWidget) -> None:
        label = QLabel(label_text)
        label.setObjectName("SummaryLabel")
        label.setFixedWidth(self.LABEL_WIDTH)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.addRow(label, field)

    def _configure_input_widget(self, widget: QWidget) -> None:
        widget.setMinimumHeight(38)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _load_companies(self, selected_company_id: int | None = None) -> None:
        self.company_input.clear()
        companies = list_company_choices()
        for company in companies:
            self.company_input.addItem(company.name, company.id)

        if selected_company_id is None:
            return

        index = self.company_input.findData(selected_company_id)
        if index >= 0:
            self.company_input.setCurrentIndex(index)

    def get_data(self) -> dict[str, Any]:
        custom_values: dict[str, object] = {}
        for section in self.dynamic_sections:
            custom_values.update(section.get_values())
        return {
            "name": self.name_input.text().strip(),
            "company_id": self.company_input.currentData(),
            "title": self.title_input.text().strip(),
            "email": self.email_input.text().strip(),
            "phone": self.phone_input.text().strip(),
            "linkedin": self.linkedin_input.text().strip(),
            "custom_values": custom_values,
        }

    def accept(self) -> None:
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Ad soyad zorunludur.")
            return

        if self.company_input.count() == 0 or self.company_input.currentData() is None:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen bir şirket seçin.")
            return

        for section in self.dynamic_sections:
            error_message = section.validate()
            if error_message:
                QMessageBox.warning(self, "Eksik Bilgi", error_message)
                return

        super().accept()
