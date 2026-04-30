from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from crm_app.models import FieldDefinition
from crm_app.services.field_service import (
    deserialize_field_value,
    get_field_values,
    list_visible_field_definitions,
    parse_options,
)


PREFERRED_TEXTAREA_KEYS = {
    "sektor",
    "kullandigi_urun",
    "potansiyel_urun",
    "kullanim_alani",
    "referans_noktasi",
    "ai_analizi",
    "satis_stratejisi",
    "onerilen_sonraki_adim",
    "kisi_genel_degerlendirme",
    "kisi_davranis_analizi",
    "kisi_ticari_yaklasim",
    "kisi_risk_notlari",
    "kisi_serbest_not",
}


class DynamicFieldsSection(QFrame):
    def __init__(
        self,
        entity_type: str,
        entity_id: int | None = None,
        show_header: bool = True,
        included_keys: set[str] | None = None,
        excluded_keys: set[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.entity_type = entity_type
        self.entity_id = entity_id
        definitions = list_visible_field_definitions(entity_type)
        if included_keys is not None:
            definitions = [definition for definition in definitions if definition.field_key in included_keys]
        if excluded_keys is not None:
            definitions = [definition for definition in definitions if definition.field_key not in excluded_keys]
        self.definitions = definitions
        self.widgets: dict[str, QWidget] = {}
        self.empty_date = QDate(2000, 1, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        if not self.definitions:
            return

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)

        values = get_field_values(entity_type, entity_id) if entity_id else {}

        for definition in self.definitions:
            widget = self._create_widget(definition)
            self._set_widget_value(widget, definition, values.get(definition.field_key))
            self.widgets[definition.field_key] = widget
            form.addRow(definition.label, widget)

        if show_header:
            title = QLabel("Ek Alanlar")
            title.setObjectName("SectionTitle")
            subtitle = QLabel("Alan Yönetimi ekranından tanımlanan dinamik alanlar")
            subtitle.setObjectName("SectionSubtitle")
            layout.addWidget(title)
            layout.addWidget(subtitle)
        layout.addLayout(form)

    def has_fields(self) -> bool:
        return bool(self.definitions)

    def get_values(self) -> dict[str, object]:
        return {
            definition.field_key: self._get_widget_value(self.widgets[definition.field_key], definition)
            for definition in self.definitions
        }

    def validate(self) -> str | None:
        for definition in self.definitions:
            if not definition.is_required:
                continue

            value = self._get_widget_value(self.widgets[definition.field_key], definition)
            if value in (None, "", []):
                return f"{definition.label} alanı zorunludur."

        return None

    def _create_widget(self, definition: FieldDefinition) -> QWidget:
        if definition.field_type == "textarea" or definition.field_key in PREFERRED_TEXTAREA_KEYS:
            widget = QTextEdit()
            widget.setFixedHeight(110 if definition.field_key in PREFERRED_TEXTAREA_KEYS else 90)
            return widget

        if definition.field_type == "number":
            widget = QLineEdit()
            widget.setValidator(QDoubleValidator(-999999999.99, 999999999.99, 2, widget))
            return widget

        if definition.field_type == "date":
            widget = QDateEdit()
            widget.setCalendarPopup(True)
            widget.setMinimumDate(self.empty_date)
            widget.setSpecialValueText("Seçilmedi")
            widget.setDate(self.empty_date)
            return widget

        if definition.field_type == "boolean":
            return QCheckBox()

        if definition.field_type == "select":
            widget = QComboBox()
            widget.addItem("Seçilmedi", "")
            for option in parse_options(definition.options_json):
                widget.addItem(option, option)
            return widget

        return QLineEdit()

    def _set_widget_value(
        self,
        widget: QWidget,
        definition: FieldDefinition,
        raw_value: str | None,
    ) -> None:
        value = deserialize_field_value(definition.field_type, raw_value or "")

        if isinstance(widget, QTextEdit):
            widget.setPlainText(str(value or ""))
        elif isinstance(widget, QLineEdit):
            widget.setText(str(value or ""))
        elif isinstance(widget, QLineEdit) and definition.field_type == "number":
            widget.setText("" if value is None else str(value))
        elif isinstance(widget, QDateEdit):
            if isinstance(value, date):
                widget.setDate(QDate(value.year, value.month, value.day))
            else:
                widget.setDate(self.empty_date)
        elif isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))
        elif isinstance(widget, QComboBox):
            index = widget.findData(value or "")
            if index >= 0:
                widget.setCurrentIndex(index)

    def _get_widget_value(self, widget: QWidget, definition: FieldDefinition) -> object:
        if isinstance(widget, QTextEdit):
            return widget.toPlainText().strip()
        if isinstance(widget, QLineEdit) and definition.field_type == "number":
            text = widget.text().strip()
            return None if not text else float(text)
        if isinstance(widget, QLineEdit):
            return widget.text().strip()
        if isinstance(widget, QDateEdit):
            return None if widget.date() == self.empty_date else widget.date().toPython()
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QComboBox):
            return widget.currentData()
        return None
