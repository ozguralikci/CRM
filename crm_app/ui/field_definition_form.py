from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
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

from crm_app.models import FieldDefinition
from crm_app.services.field_service import FIELD_TYPES, normalize_field_key, parse_options
from crm_app.ui.layout_helpers import create_scroll_area
from crm_app.ui.styles import apply_shadow, style_dialog_buttons


class FieldDefinitionFormDialog(QDialog):
    def __init__(
        self,
        definition: FieldDefinition | None = None,
        initial_entity_type: str = "company",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Alan Tanimi")
        self.setMinimumSize(620, 620)
        self._key_manually_edited = bool(definition)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header_card = QFrame()
        header_card.setObjectName("DialogCard")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(6)
        apply_shadow(header_card, blur=14, y_offset=2, alpha=10)

        title = QLabel("Alan Tanimi")
        title.setObjectName("DialogTitle")
        subtitle = QLabel("Dinamik alanlari sirket ve kisi formlarinda yonetin.")
        subtitle.setObjectName("DialogSubtitle")
        subtitle.setWordWrap(True)

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        scroll_area, _scroll_content, scroll_layout = create_scroll_area(max_content_width=760)

        card = QFrame()
        card.setObjectName("ContentCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(14)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)

        self.entity_input = QComboBox()
        self.entity_input.addItem("Sirket", "company")
        self.entity_input.addItem("Kisi", "contact")

        self.label_input = QLineEdit(definition.label if definition else "")
        self.key_input = QLineEdit(definition.field_key if definition else "")
        self.field_type_input = QComboBox()
        for field_type in FIELD_TYPES:
            self.field_type_input.addItem(field_type, field_type)
        self.required_input = QCheckBox()
        self.visible_input = QCheckBox()
        self.visible_input.setChecked(True)
        self.sort_order_input = QSpinBox()
        self.sort_order_input.setRange(0, 9999)
        self.options_input = QTextEdit()
        self.options_input.setFixedHeight(72)

        if definition:
            entity_index = self.entity_input.findData(definition.entity_type)
            if entity_index >= 0:
                self.entity_input.setCurrentIndex(entity_index)
            type_index = self.field_type_input.findData(definition.field_type)
            if type_index >= 0:
                self.field_type_input.setCurrentIndex(type_index)
            self.required_input.setChecked(definition.is_required)
            self.visible_input.setChecked(definition.is_visible)
            self.sort_order_input.setValue(definition.sort_order)
            self.options_input.setPlainText(", ".join(parse_options(definition.options_json)))
        else:
            entity_index = self.entity_input.findData(initial_entity_type)
            if entity_index >= 0:
                self.entity_input.setCurrentIndex(entity_index)

        self.label_input.textChanged.connect(self._sync_key_from_label)
        self.key_input.textEdited.connect(self._mark_key_edited)
        self.field_type_input.currentIndexChanged.connect(self._update_options_state)

        form.addRow("Varlik Tipi", self.entity_input)
        form.addRow("Alan Adi", self.label_input)
        form.addRow("Teknik Anahtar", self.key_input)
        form.addRow("Tip", self.field_type_input)
        form.addRow("Zorunlu", self.required_input)
        form.addRow("Gorunur", self.visible_input)
        form.addRow("Sira", self.sort_order_input)
        form.addRow("Secenekler", self.options_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        style_dialog_buttons(buttons)

        card_layout.addLayout(form)
        scroll_layout.addWidget(card)
        scroll_layout.addStretch()

        footer_card = QFrame()
        footer_card.setObjectName("DialogCard")
        footer_layout = QHBoxLayout(footer_card)
        footer_layout.setContentsMargins(16, 12, 16, 12)
        footer_layout.addStretch()
        footer_layout.addWidget(buttons)

        layout.addWidget(header_card)
        layout.addWidget(scroll_area, 1)
        layout.addWidget(footer_card)

        self._update_options_state()
        if not definition:
            self._sync_key_from_label(self.label_input.text())

    def _mark_key_edited(self) -> None:
        self._key_manually_edited = True

    def _sync_key_from_label(self, text: str) -> None:
        if self._key_manually_edited:
            return
        self.key_input.setText(normalize_field_key(text))

    def _update_options_state(self) -> None:
        is_select = self.field_type_input.currentData() == "select"
        self.options_input.setEnabled(is_select)
        if not is_select:
            self.options_input.clear()

    def get_data(self) -> dict[str, object]:
        return {
            "entity_type": self.entity_input.currentData(),
            "label": self.label_input.text().strip(),
            "field_key": self.key_input.text().strip(),
            "field_type": self.field_type_input.currentData(),
            "is_required": self.required_input.isChecked(),
            "is_visible": self.visible_input.isChecked(),
            "sort_order": self.sort_order_input.value(),
            "options_text": self.options_input.toPlainText().strip(),
        }

    def accept(self) -> None:
        if not self.label_input.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Alan adi zorunludur.")
            return

        if not self.key_input.text().strip():
            self.key_input.setText(normalize_field_key(self.label_input.text()))

        if self.field_type_input.currentData() == "select" and not self.options_input.toPlainText().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Select tipinde secenek girilmelidir.")
            return

        super().accept()
