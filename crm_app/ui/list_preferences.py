from __future__ import annotations

import json
from collections.abc import Callable

from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import (
    QComboBox,
    QInputDialog,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QWidget,
)

from crm_app.utils.app_paths import get_user_data_dir


def get_ui_settings() -> QSettings:
    settings_path = get_user_data_dir() / "ui-preferences.ini"
    return QSettings(str(settings_path), QSettings.Format.IniFormat)


def serialize_sort_order(order: Qt.SortOrder) -> str:
    return "desc" if order == Qt.SortOrder.DescendingOrder else "asc"


def deserialize_sort_order(value: object) -> Qt.SortOrder:
    if value in (Qt.SortOrder.AscendingOrder, "asc", "ASC", 0, "0", False):
        return Qt.SortOrder.AscendingOrder
    if value in (Qt.SortOrder.DescendingOrder, "desc", "DESC", 1, "1", True):
        return Qt.SortOrder.DescendingOrder

    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"asc", "ascending", "ascendingorder", "qt.sortorder.ascendingorder"}:
            return Qt.SortOrder.AscendingOrder
        if normalized in {"desc", "descending", "descendingorder", "qt.sortorder.descendingorder"}:
            return Qt.SortOrder.DescendingOrder
        if normalized in {"0", "1"}:
            return Qt.SortOrder.DescendingOrder if normalized == "1" else Qt.SortOrder.AscendingOrder

    if isinstance(value, (int, float)):
        return Qt.SortOrder.DescendingOrder if int(value) == 1 else Qt.SortOrder.AscendingOrder

    enum_value = getattr(value, "value", None)
    if enum_value in (0, 1):
        return Qt.SortOrder.DescendingOrder if enum_value == 1 else Qt.SortOrder.AscendingOrder

    return Qt.SortOrder.AscendingOrder


def parse_sort_section(value: object, column_count: int) -> int:
    try:
        section = int(value)
    except (TypeError, ValueError):
        return -1
    return section if 0 <= section < column_count else -1


def set_row_identifier(item, record_id: int) -> None:
    item.setData(Qt.ItemDataRole.UserRole, record_id)


def get_selected_row_identifier(table: QTableWidget) -> int | None:
    row = table.currentRow()
    if row < 0:
        return None
    item = table.item(row, 0)
    if not item:
        return None
    value = item.data(Qt.ItemDataRole.UserRole)
    return int(value) if value is not None else None


def get_selected_row_identifiers(table: QTableWidget) -> list[int]:
    selection_model = table.selectionModel()
    if selection_model is None:
        return []

    identifiers: list[int] = []
    for model_index in selection_model.selectedRows(0):
        item = table.item(model_index.row(), 0)
        if not item:
            continue
        value = item.data(Qt.ItemDataRole.UserRole)
        if value is None:
            continue
        record_id = int(value)
        if record_id not in identifiers:
            identifiers.append(record_id)
    return identifiers


class ListPagePreferences:
    def __init__(
        self,
        page_key: str,
        table: QTableWidget,
        *,
        filter_widgets: dict[str, QWidget] | None = None,
        default_visible_columns: list[int] | None = None,
        reset_callback: Callable[[], None] | None = None,
    ) -> None:
        self.page_key = page_key
        self.table = table
        self.filter_widgets = filter_widgets or {}
        self.default_visible_columns = default_visible_columns or list(range(table.columnCount()))
        self.reset_callback = reset_callback
        self.settings = get_ui_settings()
        self.column_actions: dict[int, object] = {}
        self._restoring = False
        self.view_button: QPushButton | None = None
        self.view_menu: QMenu | None = None
        self.built_in_views: dict[str, dict[str, object]] = {}
        self._applying_view = False

        header = self.table.horizontalHeader()
        header.sectionClicked.connect(self._handle_section_clicked)
        header.sectionResized.connect(self._handle_section_resized)
        header.setSortIndicatorShown(False)

        for widget in self.filter_widgets.values():
            if isinstance(widget, QLineEdit):
                widget.textChanged.connect(self.save_filter_state)
            elif isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self.save_filter_state)

    def attach_button(self, button: QPushButton) -> None:
        menu = QMenu(button)
        self.column_actions.clear()

        for column in range(self.table.columnCount()):
            header = self.table.horizontalHeaderItem(column)
            title = header.text() if header else f"Kolon {column + 1}"
            action = menu.addAction(title)
            action.setCheckable(True)
            action.setChecked(column in self.default_visible_columns)
            action.toggled.connect(
                lambda checked, col=column: self._toggle_column_visibility(col, checked)
            )
            self.column_actions[column] = action

        menu.addSeparator()
        reset_action = menu.addAction("Varsayılana Dön")
        reset_action.triggered.connect(self.reset_preferences)
        button.setMenu(menu)

    def attach_view_button(
        self,
        button: QPushButton,
        *,
        built_in_views: dict[str, dict[str, object]] | None = None,
    ) -> None:
        self.view_button = button
        self.built_in_views = built_in_views or {}
        self.view_menu = QMenu(button)
        self.view_menu.aboutToShow.connect(self._rebuild_view_menu)
        button.setMenu(self.view_menu)
        self._update_view_button_label()

    def restore(self) -> None:
        self._restoring = True
        self._apply_filter_state()
        self._apply_column_visibility()
        self._apply_sort_indicator()
        self._restoring = False

    def finalize_table_state(self) -> None:
        self._apply_column_visibility()
        self._apply_column_widths()
        self._apply_sort()

    def reset_preferences(self) -> None:
        self.settings.remove(f"{self.page_key}/filters")
        self.settings.remove(f"{self.page_key}/visible_columns")
        self.settings.remove(f"{self.page_key}/column_widths")
        self.settings.remove(f"{self.page_key}/sort_section")
        self.settings.remove(f"{self.page_key}/sort_order")
        self.settings.remove(f"{self.page_key}/active_view")
        self._update_view_button_label()
        self.restore()

        for name, widget in self.filter_widgets.items():
            if isinstance(widget, QLineEdit):
                widget.blockSignals(True)
                widget.clear()
                widget.blockSignals(False)
            elif isinstance(widget, QComboBox) and widget.count() > 0:
                widget.blockSignals(True)
                widget.setCurrentIndex(0)
                widget.blockSignals(False)

        self.save_filter_state()
        self._update_view_button_label()
        if self.reset_callback:
            self.reset_callback()

    def save_filter_state(self) -> None:
        if self._restoring:
            return
        state: dict[str, dict[str, object]] = {}
        for name, widget in self.filter_widgets.items():
            if isinstance(widget, QLineEdit):
                state[name] = {"kind": "line_edit", "text": widget.text()}
            elif isinstance(widget, QComboBox):
                state[name] = {
                    "kind": "combo_box",
                    "data": widget.currentData(),
                    "text": widget.currentText(),
                }
        self._set_json_value("filters", state)

    def save_column_widths(self) -> None:
        widths = {
            str(column): self.table.columnWidth(column)
            for column in range(self.table.columnCount())
        }
        self._set_json_value("column_widths", widths)

    def save_sort_state(self, section: int, order: Qt.SortOrder) -> None:
        self.settings.beginGroup(self.page_key)
        self.settings.setValue("sort_section", section)
        self.settings.setValue("sort_order", serialize_sort_order(order))
        self.settings.endGroup()

    def _toggle_column_visibility(self, column: int, visible: bool) -> None:
        if visible is False:
            visible_columns = [
                idx
                for idx in range(self.table.columnCount())
                if not self.table.isColumnHidden(idx) and idx != column
            ]
            if not visible_columns:
                action = self.column_actions.get(column)
                if action:
                    action.blockSignals(True)
                    action.setChecked(True)
                    action.blockSignals(False)
                return

        self.table.setColumnHidden(column, not visible)
        self._save_column_visibility()

    def _save_column_visibility(self) -> None:
        visible_columns = [
            column
            for column in range(self.table.columnCount())
            if not self.table.isColumnHidden(column)
        ]
        self._set_json_value("visible_columns", visible_columns)

    def _apply_column_visibility(self) -> None:
        visible_columns = self._get_json_value("visible_columns", self.default_visible_columns)
        visible_set = {int(column) for column in visible_columns}
        for column in range(self.table.columnCount()):
            visible = column in visible_set
            self.table.setColumnHidden(column, not visible)
            action = self.column_actions.get(column)
            if action:
                action.blockSignals(True)
                action.setChecked(visible)
                action.blockSignals(False)

    def _apply_column_widths(self) -> None:
        widths = self._get_json_value("column_widths", {})
        if not isinstance(widths, dict):
            return
        for key, width in widths.items():
            column = int(key)
            if column < self.table.columnCount():
                self.table.setColumnWidth(column, int(width))

    def _apply_filter_state(self) -> None:
        state = self._get_json_value("filters", {})
        if not isinstance(state, dict):
            return
        self._apply_filter_state_payload(state)

    def _apply_filter_state_payload(self, state: dict[str, object]) -> None:
        for name, widget in self.filter_widgets.items():
            payload = state.get(name, {})
            if isinstance(widget, QLineEdit):
                widget.blockSignals(True)
                widget.setText(str(payload.get("text", "")) if isinstance(payload, dict) else "")
                widget.blockSignals(False)
            elif isinstance(widget, QComboBox):
                widget.blockSignals(True)
                index = 0
                if isinstance(payload, dict):
                    data_value = payload.get("data")
                    index = widget.findData(data_value)
                    if index < 0:
                        text_value = str(payload.get("text", ""))
                        index = widget.findText(text_value)
                widget.setCurrentIndex(index if index >= 0 else 0)
                widget.blockSignals(False)

    def _handle_section_resized(self, _index: int, _old_size: int, _new_size: int) -> None:
        if self._restoring:
            return
        self.save_column_widths()

    def _handle_section_clicked(self, section: int) -> None:
        current_section = parse_sort_section(
            self.settings.value(f"{self.page_key}/sort_section", -1),
            self.table.columnCount(),
        )
        current_order = deserialize_sort_order(
            self.settings.value(f"{self.page_key}/sort_order", "asc")
        )
        next_order = (
            Qt.SortOrder.DescendingOrder
            if current_section == section and current_order == Qt.SortOrder.AscendingOrder
            else Qt.SortOrder.AscendingOrder
        )
        self.save_sort_state(section, next_order)
        self._apply_sort()

    def _apply_sort_indicator(self) -> None:
        section = parse_sort_section(
            self.settings.value(f"{self.page_key}/sort_section", -1),
            self.table.columnCount(),
        )
        if section < 0 or self.table.isColumnHidden(section):
            self.table.horizontalHeader().setSortIndicatorShown(False)
            return
        order = deserialize_sort_order(
            self.settings.value(f"{self.page_key}/sort_order", "asc")
        )
        self.table.horizontalHeader().setSortIndicator(section, order)
        self.table.horizontalHeader().setSortIndicatorShown(True)

    def _apply_sort(self) -> None:
        section = parse_sort_section(
            self.settings.value(f"{self.page_key}/sort_section", -1),
            self.table.columnCount(),
        )
        if section < 0 or self.table.isColumnHidden(section):
            self.table.horizontalHeader().setSortIndicatorShown(False)
            return
        order = deserialize_sort_order(
            self.settings.value(f"{self.page_key}/sort_order", "asc")
        )
        self.table.sortItems(section, order)
        self.table.horizontalHeader().setSortIndicator(section, order)
        self.table.horizontalHeader().setSortIndicatorShown(True)

    def _get_json_value(self, key: str, default: object) -> object:
        raw_value = self.settings.value(f"{self.page_key}/{key}", "")
        if not raw_value:
            return default
        try:
            return json.loads(raw_value)
        except json.JSONDecodeError:
            return default

    def _set_json_value(self, key: str, value: object) -> None:
        self.settings.setValue(f"{self.page_key}/{key}", json.dumps(value))

    def _capture_filter_state(self) -> dict[str, dict[str, object]]:
        state: dict[str, dict[str, object]] = {}
        for name, widget in self.filter_widgets.items():
            if isinstance(widget, QLineEdit):
                state[name] = {"kind": "line_edit", "text": widget.text()}
            elif isinstance(widget, QComboBox):
                state[name] = {
                    "kind": "combo_box",
                    "data": widget.currentData(),
                    "text": widget.currentText(),
                }
        return state

    def _capture_current_view_state(self) -> dict[str, object]:
        header = self.table.horizontalHeader()
        section = parse_sort_section(
            self.settings.value(f"{self.page_key}/sort_section", header.sortIndicatorSection()),
            self.table.columnCount(),
        )
        order = deserialize_sort_order(
            self.settings.value(f"{self.page_key}/sort_order", header.sortIndicatorOrder())
        )
        return {
            "filters": self._capture_filter_state(),
            "visible_columns": [
                column
                for column in range(self.table.columnCount())
                if not self.table.isColumnHidden(column)
            ],
            "column_widths": {
                str(column): self.table.columnWidth(column)
                for column in range(self.table.columnCount())
            },
            "sort_section": section,
            "sort_order": serialize_sort_order(order),
        }

    def _normalize_view_state(self, state: dict[str, object] | None) -> dict[str, object]:
        state = state or {}
        visible_columns = state.get("visible_columns", self.default_visible_columns)
        if not isinstance(visible_columns, list):
            visible_columns = self.default_visible_columns

        column_widths = state.get("column_widths", {})
        if not isinstance(column_widths, dict):
            column_widths = {}

        sort_section = parse_sort_section(state.get("sort_section", -1), self.table.columnCount())
        sort_order = serialize_sort_order(deserialize_sort_order(state.get("sort_order", "asc")))

        filters = state.get("filters", {})
        if not isinstance(filters, dict):
            filters = {}

        return {
            "filters": filters,
            "visible_columns": visible_columns,
            "column_widths": column_widths,
            "sort_section": sort_section,
            "sort_order": sort_order,
        }

    def _write_view_state(self, state: dict[str, object]) -> None:
        normalized = self._normalize_view_state(state)
        self._set_json_value("filters", normalized["filters"])
        self._set_json_value("visible_columns", normalized["visible_columns"])
        self._set_json_value("column_widths", normalized["column_widths"])
        self.settings.setValue(f"{self.page_key}/sort_section", normalized["sort_section"])
        self.settings.setValue(f"{self.page_key}/sort_order", normalized["sort_order"])

    def _get_saved_view_presets(self) -> dict[str, dict[str, object]]:
        data = self._get_json_value("view_presets", {})
        if not isinstance(data, dict):
            return {}
        presets: dict[str, dict[str, object]] = {}
        for name, payload in data.items():
            if isinstance(name, str) and isinstance(payload, dict):
                presets[name] = self._normalize_view_state(payload)
        return presets

    def _save_view_presets(self, presets: dict[str, dict[str, object]]) -> None:
        self._set_json_value("view_presets", presets)

    def _set_active_view(self, key: str | None) -> None:
        if key:
            self.settings.setValue(f"{self.page_key}/active_view", key)
        else:
            self.settings.remove(f"{self.page_key}/active_view")
        self._update_view_button_label()

    def _get_active_view(self) -> str:
        return str(self.settings.value(f"{self.page_key}/active_view", ""))

    def _update_view_button_label(self) -> None:
        if not self.view_button:
            return
        active_view = self._get_active_view()
        label = "Görünümler"
        if active_view.startswith("builtin:"):
            label = f"Görünümler: {active_view.removeprefix('builtin:')}"
        elif active_view.startswith("saved:"):
            label = f"Görünümler: {active_view.removeprefix('saved:')}"
        self.view_button.setText(label)

    def _apply_view_state(self, state: dict[str, object], active_view_key: str | None) -> None:
        self._applying_view = True
        try:
            self._write_view_state(state)
            self._set_active_view(active_view_key)
            self.restore()
            if self.reset_callback:
                self.reset_callback()
            else:
                self.finalize_table_state()
        finally:
            self._applying_view = False

    def _save_current_view(self) -> None:
        name, accepted = QInputDialog.getText(
            self.view_button or self.table,
            "Görünümü Kaydet",
            "Görünüm adı:",
        )
        if not accepted or not name.strip():
            return
        presets = self._get_saved_view_presets()
        preset_name = name.strip()
        presets[preset_name] = self._normalize_view_state(self._capture_current_view_state())
        self._save_view_presets(presets)
        self._set_active_view(f"saved:{preset_name}")

    def _update_current_view(self) -> None:
        active_view = self._get_active_view()
        if not active_view.startswith("saved:"):
            return
        preset_name = active_view.removeprefix("saved:")
        presets = self._get_saved_view_presets()
        if preset_name not in presets:
            return
        presets[preset_name] = self._normalize_view_state(self._capture_current_view_state())
        self._save_view_presets(presets)
        self._set_active_view(active_view)

    def _delete_current_view(self) -> None:
        active_view = self._get_active_view()
        if not active_view.startswith("saved:"):
            return
        preset_name = active_view.removeprefix("saved:")
        presets = self._get_saved_view_presets()
        if preset_name not in presets:
            return
        answer = QMessageBox.question(
            self.view_button or self.table,
            "Görünümü Sil",
            f"{preset_name} görünümü silinsin mi?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        del presets[preset_name]
        self._save_view_presets(presets)
        self._set_active_view(None)

    def _rebuild_view_menu(self) -> None:
        if not self.view_menu:
            return
        self.view_menu.clear()

        save_action = self.view_menu.addAction("Görünümü Kaydet")
        save_action.triggered.connect(self._save_current_view)

        active_view = self._get_active_view()
        update_action = self.view_menu.addAction("Görünümü Güncelle")
        update_action.setEnabled(active_view.startswith("saved:"))
        update_action.triggered.connect(self._update_current_view)

        delete_action = self.view_menu.addAction("Görünümü Sil")
        delete_action.setEnabled(active_view.startswith("saved:"))
        delete_action.triggered.connect(self._delete_current_view)

        self.view_menu.addSeparator()
        default_action = self.view_menu.addAction("Varsayılan Görünüm")
        default_action.setCheckable(True)
        default_action.setChecked(not active_view)
        default_action.triggered.connect(self.reset_preferences)

        built_in_views = self.built_in_views
        if built_in_views:
            built_in_menu = self.view_menu.addMenu("Hazır Görünümler")
            for name, state in built_in_views.items():
                action = built_in_menu.addAction(name)
                action.setCheckable(True)
                action.setChecked(active_view == f"builtin:{name}")
                action.triggered.connect(
                    lambda _checked=False, view_name=name, view_state=state: self._apply_view_state(
                        view_state,
                        f"builtin:{view_name}",
                    )
                )

        saved_views = self._get_saved_view_presets()
        if saved_views:
            saved_menu = self.view_menu.addMenu("Kaydedilen Görünümler")
            for name, state in saved_views.items():
                action = saved_menu.addAction(name)
                action.setCheckable(True)
                action.setChecked(active_view == f"saved:{name}")
                action.triggered.connect(
                    lambda _checked=False, view_name=name, view_state=state: self._apply_view_state(
                        view_state,
                        f"saved:{view_name}",
                    )
                )
