from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crm_app.models import FieldDefinition
from crm_app.services.field_service import (
    delete_field_definition,
    list_field_definitions,
    move_field_definition,
    update_field_definition,
    create_field_definition,
)
from crm_app.ui.field_definition_form import FieldDefinitionFormDialog
from crm_app.ui.list_page_helpers import (
    create_list_page_toolbar,
    create_list_table_card,
    set_table_empty_state,
)
from crm_app.ui.list_preferences import (
    ListPagePreferences,
    get_selected_row_identifier,
    set_row_identifier,
)
from crm_app.ui.styles import (
    configure_table,
    create_page_header,
    set_button_role,
)


class FieldManagementPage(QWidget):
    headers = ["Sıra", "Alan Adı", "Teknik Anahtar", "Tip", "Zorunlu", "Görünür", "Varlık Tipi"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.definitions: list[FieldDefinition] = []

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(12)

        root_layout.addWidget(
            create_page_header(
                "Alan Yönetimi",
                "Şirket ve kişi formlarına eklenecek dinamik alanları yönetin.",
            )
        )

        self.entity_filter = QComboBox()
        self.entity_filter.setMinimumWidth(120)
        self.entity_filter.addItem("Şirket", "company")
        self.entity_filter.addItem("Kişi", "contact")
        self.entity_filter.currentIndexChanged.connect(self.refresh_table)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Alan adı veya teknik anahtar ara...")
        self.search_input.textChanged.connect(self.refresh_table)

        add_button = QPushButton("Yeni Alan")
        columns_button = QPushButton("Kolonlar")
        edit_button = QPushButton("Düzenle")
        delete_button = QPushButton("Sil")
        up_button = QPushButton("Yukarı")
        down_button = QPushButton("Aşağı")
        refresh_button = QPushButton("Yenile")

        set_button_role(add_button, "primary")
        set_button_role(columns_button, "ghost")
        set_button_role(edit_button, "secondary")
        set_button_role(delete_button, "danger")
        set_button_role(up_button, "ghost")
        set_button_role(down_button, "ghost")
        set_button_role(refresh_button, "ghost")

        add_button.clicked.connect(self.add_definition)
        edit_button.clicked.connect(self.edit_selected_definition)
        delete_button.clicked.connect(self.delete_selected_definition)
        up_button.clicked.connect(lambda: self.move_selected_definition("up"))
        down_button.clicked.connect(lambda: self.move_selected_definition("down"))
        refresh_button.clicked.connect(self.refresh_table)

        entity_label = QLabel("Varlık")
        entity_label.setObjectName("SummaryLabel")
        toolbar_card = create_list_page_toolbar(
            "Dinamik Alanlar",
            "Görünürlük, sıra ve zorunluluk ayarlarını yönetin",
            top_actions=[
                add_button,
                columns_button,
                edit_button,
                delete_button,
                up_button,
                down_button,
                refresh_button,
            ],
            search_widget=self.search_input,
            filter_widgets=[entity_label, self.entity_filter],
        )

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemDoubleClicked.connect(self.edit_selected_definition)
        configure_table(self.table)
        self.preferences = ListPagePreferences(
            "field_management",
            self.table,
            filter_widgets={
                "search": self.search_input,
                "entity": self.entity_filter,
            },
            default_visible_columns=list(range(len(self.headers))),
            reset_callback=self.refresh_table,
        )
        self.preferences.attach_button(columns_button)

        table_card = create_list_table_card(self.table)

        root_layout.addWidget(toolbar_card)
        root_layout.addWidget(table_card, 1)

        self.preferences.restore()
        self.refresh_table()

    def refresh_table(self) -> None:
        entity_type = self.entity_filter.currentData()
        self.definitions = list_field_definitions(
            entity_type=entity_type,
            search_text=self.search_input.text().strip(),
        )
        self.table.setRowCount(len(self.definitions))

        if not self.definitions:
            set_table_empty_state(
                self.table,
                "Arama ve seçili varlık tipine uygun alan tanımı bulunamadı.",
                action_label="Yeni Alan",
                action_handler=self.add_definition,
            )
            self.preferences.finalize_table_state()
            return

        key_font = QFont("Segoe UI", 9)
        key_font.setBold(True)
        for row, definition in enumerate(self.definitions):
            values = [
                str(definition.sort_order),
                definition.label,
                definition.field_key,
                definition.field_type,
                "Evet" if definition.is_required else "Hayır",
                "Evet" if definition.is_visible else "Hayır",
                "Şirket" if definition.entity_type == "company" else "Kişi",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                if column == 1:
                    item.setFont(key_font)
                    item.setForeground(QColor("#11243a"))
                elif column in {2, 3, 6}:
                    item.setForeground(QColor("#5f7188"))
                if column == 0:
                    set_row_identifier(item, definition.id)
                self.table.setItem(row, column, item)

        self.table.resizeColumnsToContents()
        self.preferences.finalize_table_state()

    def add_definition(self) -> None:
        dialog = FieldDefinitionFormDialog(
            initial_entity_type=self.entity_filter.currentData(),
            parent=self,
        )
        if dialog.exec():
            try:
                create_field_definition(dialog.get_data())
            except ValueError as exc:
                self._notify(str(exc), error=True)
                return
            self.refresh_table()
            self._notify("Alan tanımı oluşturuldu.")

    def edit_selected_definition(self, _item: QTableWidgetItem | None = None) -> None:
        definition = self._get_selected_definition()
        if not definition:
            self._notify("Lütfen bir alan seçin.", error=True)
            return

        dialog = FieldDefinitionFormDialog(definition=definition, parent=self)
        if dialog.exec():
            try:
                update_field_definition(definition.id, dialog.get_data())
            except ValueError as exc:
                self._notify(str(exc), error=True)
                return
            self.refresh_table()
            self._notify("Alan tanımı güncellendi.")

    def delete_selected_definition(self) -> None:
        definition = self._get_selected_definition()
        if not definition:
            self._notify("Lütfen bir alan seçin.", error=True)
            return

        answer = QMessageBox.question(
            self,
            "Alan Sil",
            f"{definition.label} alanını silmek istiyor musunuz?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            delete_field_definition(definition.id)
            self.refresh_table()
            self._notify("Alan tanımı silindi.")

    def move_selected_definition(self, direction: str) -> None:
        definition = self._get_selected_definition()
        if not definition:
            self._notify("Lütfen bir alan seçin.", error=True)
            return

        move_field_definition(definition.id, direction)
        self.refresh_table()

    def _get_selected_definition(self) -> FieldDefinition | None:
        definition_id = get_selected_row_identifier(self.table)
        if definition_id is None:
            return None
        return next(
            (definition for definition in self.definitions if definition.id == definition_id),
            None,
        )

    def _notify(self, message: str, error: bool = False) -> None:
        box = QMessageBox.warning if error else QMessageBox.information
        box(self, "Bilgi", message)
