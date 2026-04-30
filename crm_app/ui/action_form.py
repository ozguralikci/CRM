from __future__ import annotations

from datetime import date, datetime

from PySide6.QtCore import QDate, QTime, Qt
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
    QTextEdit,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from crm_app.models import Action
from crm_app.services.action_service import list_action_types, list_channels
from crm_app.services.contact_service import list_company_choices, list_contact_choices
from crm_app.ui.layout_helpers import create_scroll_area
from crm_app.ui.styles import apply_shadow, create_content_card, style_dialog_buttons


class ActionFormDialog(QDialog):
    def __init__(
        self,
        action: Action | None = None,
        initial_company_id: int | None = None,
        initial_contact_id: int | None = None,
        initial_record_type: str = "Sirket",
        initial_action_type: str = "",
        initial_channel: str = "",
        initial_note: str = "",
        initial_result: str = "",
        initial_next_action: str = "",
        initial_next_action_date: date | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Aksiyon")
        self.setMinimumSize(720, 760)

        self.empty_next_action_date = QDate(2000, 1, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header_card = QFrame()
        header_card.setObjectName("DialogCard")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(6)
        apply_shadow(header_card, blur=14, y_offset=2, alpha=10)

        title = QLabel("Aksiyon Kaydı")
        title.setObjectName("DialogTitle")
        subtitle = QLabel("Şirket ve kişi bazlı satış temaslarını tek formdan yönetin.")
        subtitle.setObjectName("DialogSubtitle")
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        scroll_area, _scroll_content, scroll_layout = create_scroll_area(max_content_width=900)

        self.record_type_input = QComboBox()
        self.record_type_input.addItems(["Şirket", "Kişi"])

        self.company_input = QComboBox()
        self.contact_input = QComboBox()

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())

        self.time_input = QTimeEdit()
        self.time_input.setDisplayFormat("HH:mm")
        self.time_input.setTime(QTime.currentTime())

        self.action_type_input = QComboBox()
        self.action_type_input.setEditable(True)
        self.channel_input = QComboBox()
        self.channel_input.setEditable(True)

        self.note_input = QTextEdit()
        self.note_input.setMinimumHeight(150)
        self.result_input = QLineEdit()
        self.next_action_input = QLineEdit()

        self.next_action_date_input = QDateEdit()
        self.next_action_date_input.setCalendarPopup(True)
        self.next_action_date_input.setMinimumDate(self.empty_next_action_date)
        self.next_action_date_input.setSpecialValueText("Seçilmedi")
        self.next_action_date_input.setDate(self.empty_next_action_date)

        selected_company_id = action.company_id if action else initial_company_id
        self._load_companies(selected_company_id=selected_company_id)
        self._load_contact_choices(
            selected_company_id=action.company_id if action else self.company_input.currentData(),
            selected_contact_id=action.contact_id if action else initial_contact_id,
        )
        self._load_common_values()

        if action:
            self.record_type_input.setCurrentText("Kişi" if action.contact_id else "Şirket")
            self.date_input.setDate(QDate(action.created_at.year, action.created_at.month, action.created_at.day))
            self.time_input.setTime(QTime(action.created_at.hour, action.created_at.minute))
            self.action_type_input.setCurrentText(action.action_type)
            self.channel_input.setCurrentText(action.channel)
            self.note_input.setPlainText(action.note or "")
            self.result_input.setText(action.result or "")
            self.next_action_input.setText(action.next_action or "")
            if action.next_action_date:
                self.next_action_date_input.setDate(
                    QDate(
                        action.next_action_date.year,
                        action.next_action_date.month,
                        action.next_action_date.day,
                    )
                )
        else:
            self.record_type_input.setCurrentText(
                "Kişi" if initial_record_type == "Kisi" else "Şirket"
            )
            if initial_action_type:
                self.action_type_input.setCurrentText(initial_action_type)
            if initial_channel:
                self.channel_input.setCurrentText(initial_channel)
            if initial_note:
                self.note_input.setPlainText(initial_note)
            if initial_result:
                self.result_input.setText(initial_result)
            if initial_next_action:
                self.next_action_input.setText(initial_next_action)
            if initial_next_action_date:
                self.next_action_date_input.setDate(
                    QDate(
                        initial_next_action_date.year,
                        initial_next_action_date.month,
                        initial_next_action_date.day,
                    )
                )

        record_form = QFormLayout()
        record_form.setHorizontalSpacing(18)
        record_form.setVerticalSpacing(12)
        record_form.addRow("Kayıt Tipi", self.record_type_input)
        record_form.addRow("Şirket", self.company_input)
        record_form.addRow("Kişi", self.contact_input)
        scroll_layout.addWidget(
            self._create_form_section(
                "Kayıt Bilgisi",
                "Aksiyonun bağlı olduğu kayıt türünü ve şirket bilgisini seçin.",
                record_form,
            )
        )

        detail_form = QFormLayout()
        detail_form.setHorizontalSpacing(18)
        detail_form.setVerticalSpacing(12)
        detail_form.addRow("Tarih", self.date_input)
        detail_form.addRow("Saat", self.time_input)
        detail_form.addRow("Aksiyon Tipi", self.action_type_input)
        detail_form.addRow("Kanal", self.channel_input)
        detail_form.addRow("Sonuç", self.result_input)
        scroll_layout.addWidget(
            self._create_form_section(
                "Aksiyon Detayı",
                "Temasın zamanı, kanalı ve sonucunu kaydedin.",
                detail_form,
            )
        )

        follow_up_form = QFormLayout()
        follow_up_form.setHorizontalSpacing(18)
        follow_up_form.setVerticalSpacing(12)
        follow_up_form.addRow("Sonraki Aksiyon", self.next_action_input)
        follow_up_form.addRow("Sonraki Aksiyon Tarihi", self.next_action_date_input)
        scroll_layout.addWidget(
            self._create_form_section(
                "Takip Planı",
                "Bir sonraki aksiyonu ve planlanan takip tarihini belirleyin.",
                follow_up_form,
            )
        )

        note_card = create_content_card()
        note_layout = QVBoxLayout(note_card)
        note_layout.setContentsMargins(16, 16, 16, 16)
        note_layout.setSpacing(10)
        note_title = QLabel("Notlar")
        note_title.setObjectName("SectionTitle")
        note_subtitle = QLabel("Görüşme detaylarını, önemli bağlamı ve satış notlarını kaydedin.")
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

        self.record_type_input.currentIndexChanged.connect(self._update_record_type_state)
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

        self._update_record_type_state()

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

    def _load_common_values(self) -> None:
        action_types = ["Arama", "Toplanti", "E-posta", "Ziyaret", "Teklif Takibi"]
        channels = ["Telefon", "E-posta", "WhatsApp", "Toplanti", "LinkedIn"]

        self.action_type_input.clear()
        self.channel_input.clear()

        for value in action_types + [item for item in list_action_types() if item not in action_types]:
            self.action_type_input.addItem(value)

        for value in channels + [item for item in list_channels() if item not in channels]:
            self.channel_input.addItem(value)

    def _load_companies(self, selected_company_id: int | None = None) -> None:
        self.company_input.clear()
        for company in list_company_choices():
            self.company_input.addItem(company.name, company.id)

        if selected_company_id is not None:
            index = self.company_input.findData(selected_company_id)
            if index >= 0:
                self.company_input.setCurrentIndex(index)

    def _load_contact_choices(
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

    def _on_company_changed(self) -> None:
        self._load_contact_choices(selected_company_id=self.company_input.currentData())
        self._update_record_type_state()

    def _update_record_type_state(self) -> None:
        is_contact_mode = self.record_type_input.currentText() == "Kişi"
        self.contact_input.setEnabled(is_contact_mode)
        if not is_contact_mode:
            self.contact_input.setCurrentIndex(0)

    def get_data(self) -> dict[str, object]:
        created_at = datetime.combine(
            self.date_input.date().toPython(),
            self.time_input.time().toPython(),
        )
        next_action_date = self.next_action_date_input.date().toPython()
        if self.next_action_date_input.date() == self.empty_next_action_date:
            next_action_date = None

        contact_id = self.contact_input.currentData()
        if self.record_type_input.currentText() == "Şirket":
            contact_id = None

        return {
            "company_id": self.company_input.currentData(),
            "contact_id": contact_id,
            "created_at": created_at,
            "action_type": self.action_type_input.currentText().strip(),
            "channel": self.channel_input.currentText().strip(),
            "note": self.note_input.toPlainText().strip(),
            "result": self.result_input.text().strip(),
            "next_action": self.next_action_input.text().strip(),
            "next_action_date": next_action_date,
        }

    def accept(self) -> None:
        if self.company_input.count() == 0 or self.company_input.currentData() is None:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen bir şirket seçin.")
            return

        if not self.action_type_input.currentText().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Aksiyon tipi zorunludur.")
            return

        if self.record_type_input.currentText() == "Kişi" and self.contact_input.currentData() is None:
            QMessageBox.warning(self, "Eksik Bilgi", "Kişi tipi için kişi seçilmelidir.")
            return

        super().accept()
