from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crm_app.models import Action
from crm_app.services.export_service import export_rows
from crm_app.services.action_service import (
    create_action,
    delete_action,
    get_action,
    list_action_types,
    list_actions,
    list_channels,
    update_action,
)
from crm_app.ui.action_form import ActionFormDialog
from crm_app.ui.bulk_actions import (
    BulkDateDialog,
    confirm_bulk_action,
    create_bulk_action_controls,
    show_bulk_result,
    update_bulk_action_controls,
)
from crm_app.ui.list_page_helpers import (
    create_list_page_toolbar,
    create_list_table_card,
    set_table_empty_state,
)
from crm_app.ui.list_preferences import (
    ListPagePreferences,
    get_selected_row_identifier,
    get_selected_row_identifiers,
    set_row_identifier,
)
from crm_app.ui.styles import (
    configure_table,
    create_page_header,
    set_button_role,
)
from crm_app.utils.app_paths import get_default_export_path


class ActionsPage(QWidget):
    headers = [
        "Tarih",
        "Saat",
        "Kayit Tipi",
        "Sirket",
        "Kisi",
        "Aksiyon Tipi",
        "Kanal",
        "Sonuc",
        "Sonraki Aksiyon",
        "Sonraki Aksiyon Tarihi",
    ]
    export_headers = [
        "Tarih",
        "Saat",
        "Kayit Tipi",
        "Sirket",
        "Kisi",
        "Aksiyon Tipi",
        "Kanal",
        "Sonuc",
        "Sonraki Aksiyon",
        "Sonraki Aksiyon Tarihi",
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.actions: list[Action] = []

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(12)

        root_layout.addWidget(
            create_page_header(
                "Aksiyonlar",
                "Tum satis etkileşimlerini, takiplerini ve sonraki adimlari tek merkezde izleyin.",
            )
        )

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Aksiyon notu, sonuc veya tipine gore ara...")
        self.search_input.textChanged.connect(self.refresh_table)

        self.record_type_filter = QComboBox()
        self.record_type_filter.addItem("Tum Kayit Tipleri", "")
        self.record_type_filter.addItem("Sirket", "Sirket")
        self.record_type_filter.addItem("Kisi", "Kisi")
        self.record_type_filter.setMinimumWidth(140)
        self.record_type_filter.currentIndexChanged.connect(self.refresh_table)

        self.action_type_filter = QComboBox()
        self.action_type_filter.setMinimumWidth(150)
        self.action_type_filter.currentIndexChanged.connect(self.refresh_table)

        self.channel_filter = QComboBox()
        self.channel_filter.setMinimumWidth(140)
        self.channel_filter.currentIndexChanged.connect(self.refresh_table)

        self.bulk_count_label, self.bulk_button = create_bulk_action_controls()
        self.bulk_menu = QMenu(self.bulk_button)
        self.bulk_menu.addAction("Toplu Sonraki Aksiyon Tarihi Güncelle", self.bulk_update_next_action_date)
        self.bulk_menu.addAction("Toplu Sonuç Güncelle", self.bulk_update_result)
        self.bulk_menu.addAction("Toplu Kanal Güncelle", self.bulk_update_channel)
        self.bulk_button.setMenu(self.bulk_menu)

        add_button = QPushButton("Ekle")
        views_button = QPushButton("Görünümler")
        columns_button = QPushButton("Kolonlar")
        edit_button = QPushButton("Duzenle")
        delete_button = QPushButton("Sil")
        refresh_button = QPushButton("Yenile")
        export_button = QPushButton("Disa Aktar")
        set_button_role(add_button, "primary")
        set_button_role(views_button, "ghost")
        set_button_role(columns_button, "ghost")
        set_button_role(edit_button, "secondary")
        set_button_role(delete_button, "danger")
        set_button_role(refresh_button, "ghost")
        set_button_role(export_button, "ghost")

        add_button.clicked.connect(self.add_action)
        edit_button.clicked.connect(self.edit_selected_action)
        delete_button.clicked.connect(self.delete_selected_action)
        refresh_button.clicked.connect(self.refresh_table)
        export_button.clicked.connect(self.export_actions_file)

        toolbar_card = create_list_page_toolbar(
            "Aksiyon Takibi",
            "Filtreleme, guncelleme ve hizli takip islemleri",
            top_actions=[
                add_button,
                self.bulk_count_label,
                self.bulk_button,
                views_button,
                columns_button,
                edit_button,
                delete_button,
                refresh_button,
                export_button,
            ],
            search_widget=self.search_input,
            filter_widgets=[self.record_type_filter, self.action_type_filter, self.channel_filter],
        )

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemDoubleClicked.connect(self.edit_selected_action)
        configure_table(self.table)
        self.table.itemSelectionChanged.connect(self._update_bulk_actions_state)
        self.preferences = ListPagePreferences(
            "actions",
            self.table,
            filter_widgets={
                "search": self.search_input,
                "record_type": self.record_type_filter,
                "action_type": self.action_type_filter,
                "channel": self.channel_filter,
            },
            default_visible_columns=list(range(len(self.headers))),
            reset_callback=self.refresh_table,
        )
        self.preferences.attach_button(columns_button)
        self.preferences.attach_view_button(views_button)

        table_card = create_list_table_card(self.table)

        root_layout.addWidget(toolbar_card)
        root_layout.addWidget(table_card, 1)

        self.refresh_filter_options()
        self.preferences.restore()
        self.refresh_table()

    def refresh_filter_options(self) -> None:
        current_action_type = self.action_type_filter.currentData()
        current_channel = self.channel_filter.currentData()

        self.action_type_filter.blockSignals(True)
        self.channel_filter.blockSignals(True)

        self.action_type_filter.clear()
        self.action_type_filter.addItem("Tum Aksiyon Tipleri", "")
        for item in list_action_types():
            self.action_type_filter.addItem(item, item)

        self.channel_filter.clear()
        self.channel_filter.addItem("Tum Kanallar", "")
        for item in list_channels():
            self.channel_filter.addItem(item, item)

        if current_action_type:
            index = self.action_type_filter.findData(current_action_type)
            if index >= 0:
                self.action_type_filter.setCurrentIndex(index)

        if current_channel:
            index = self.channel_filter.findData(current_channel)
            if index >= 0:
                self.channel_filter.setCurrentIndex(index)

        self.action_type_filter.blockSignals(False)
        self.channel_filter.blockSignals(False)

    def refresh_table(self) -> None:
        self.refresh_filter_options()
        self.actions = list_actions(
            search_text=self.search_input.text().strip(),
            record_type=self.record_type_filter.currentData(),
            action_type=self.action_type_filter.currentData(),
            channel=self.channel_filter.currentData(),
        )
        self.table.setRowCount(len(self.actions))

        if not self.actions:
            set_table_empty_state(
                self.table,
                "Arama ve filtrelere uygun aksiyon kaydı bulunamadı.",
                action_label="Yeni Aksiyon",
                action_handler=self.add_action,
            )
            self.preferences.finalize_table_state()
            self._update_bulk_actions_state()
            return

        primary_font = QFont("Segoe UI", 9)
        primary_font.setBold(True)

        for row, action in enumerate(self.actions):
            values = [
                action.created_at.strftime("%d.%m.%Y"),
                action.created_at.strftime("%H:%M"),
                "Kisi" if action.contact_id else "Sirket",
                action.company.name if action.company else "-",
                action.contact.name if action.contact else "-",
                action.action_type or "-",
                action.channel or "-",
                action.result or "-",
                action.next_action or "-",
                action.next_action_date.strftime("%d.%m.%Y") if action.next_action_date else "-",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                if column in {5, 8}:
                    item.setFont(primary_font)
                    item.setForeground(QColor("#11243a"))
                elif column in {0, 1, 2, 6, 7, 9}:
                    item.setForeground(QColor("#5f7188"))
                if column == 0:
                    set_row_identifier(item, action.id)
                self.table.setItem(row, column, item)

        self.table.resizeColumnsToContents()
        self.preferences.finalize_table_state()
        self._update_bulk_actions_state()

    def add_action(self) -> None:
        dialog = ActionFormDialog(parent=self)
        if dialog.exec():
            create_action(dialog.get_data())
            self.refresh_table()
            self._notify("Aksiyon kaydi olusturuldu.")

    def export_actions_file(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Aksiyonlari Disa Aktar",
            get_default_export_path("aksiyonlar.csv"),
            "CSV Dosyalari (*.csv);;Excel Dosyalari (*.xlsx)",
        )
        if not file_path:
            return

        rows = [
            [
                action.created_at.strftime("%d.%m.%Y"),
                action.created_at.strftime("%H:%M"),
                "Kisi" if action.contact_id else "Sirket",
                action.company.name if action.company else "",
                action.contact.name if action.contact else "",
                action.action_type or "",
                action.channel or "",
                action.result or "",
                action.next_action or "",
                action.next_action_date.strftime("%d.%m.%Y") if action.next_action_date else "",
            ]
            for action in self.actions
        ]
        export_rows(file_path, self.export_headers, rows)
        self._notify("Aksiyon listesi disa aktarildi.")

    def edit_selected_action(self, _item: QTableWidgetItem | None = None) -> None:
        action = self._get_selected_action()
        if not action:
            self._notify("Lutfen bir aksiyon secin.", error=True)
            return

        fresh_action = get_action(action.id)
        if not fresh_action:
            self._notify("Aksiyon kaydi bulunamadi.", error=True)
            return

        dialog = ActionFormDialog(action=fresh_action, parent=self)
        if dialog.exec():
            update_action(fresh_action.id, dialog.get_data())
            self.refresh_table()
            self._notify("Aksiyon kaydi guncellendi.")

    def delete_selected_action(self) -> None:
        action = self._get_selected_action()
        if not action:
            self._notify("Lutfen bir aksiyon secin.", error=True)
            return

        answer = QMessageBox.question(
            self,
            "Aksiyon Sil",
            "Secili aksiyon kaydini silmek istiyor musunuz?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            delete_action(action.id)
            self.refresh_table()
            self._notify("Aksiyon kaydi silindi.")

    def _get_selected_action(self) -> Action | None:
        selected_ids = get_selected_row_identifiers(self.table)
        if len(selected_ids) != 1:
            return None
        action_id = selected_ids[0]
        if action_id is None:
            return None
        return next((action for action in self.actions if action.id == action_id), None)

    def _get_selected_actions(self) -> list[Action]:
        selected_ids = get_selected_row_identifiers(self.table)
        selected_map = {action.id: action for action in self.actions}
        return [selected_map[action_id] for action_id in selected_ids if action_id in selected_map]

    def _update_bulk_actions_state(self) -> None:
        update_bulk_action_controls(self.bulk_count_label, self.bulk_button, len(self._get_selected_actions()))

    def _apply_bulk_action(self, action_label: str, callback) -> None:
        actions = self._get_selected_actions()
        if len(actions) < 2:
            self._notify("Toplu işlem için en az iki aksiyon seçin.", error=True)
            return
        if not confirm_bulk_action(self, action_label, len(actions)):
            return

        success_count = 0
        failures: list[str] = []
        for action in actions:
            try:
                callback(action)
                success_count += 1
            except Exception as exc:
                failures.append(f"{action.action_type or action.id}: {exc}")

        self.refresh_table()
        show_bulk_result(self, success_count=success_count, failures=failures)

    def bulk_update_next_action_date(self) -> None:
        dialog = BulkDateDialog("Toplu Takip Tarihi", "Sonraki aksiyon tarihi:", self)
        if not dialog.exec():
            return
        target_date = dialog.get_value()
        self._apply_bulk_action(
            "Toplu Sonraki Aksiyon Tarihi Güncelle",
            lambda action: update_action(action.id, {"next_action_date": target_date}),
        )

    def bulk_update_result(self) -> None:
        result_text, accepted = QInputDialog.getText(
            self,
            "Toplu Sonuç Güncelle",
            "Yeni sonuç:",
        )
        if not accepted or not result_text.strip():
            return
        self._apply_bulk_action(
            "Toplu Sonuç Güncelle",
            lambda action: update_action(action.id, {"result": result_text.strip()}),
        )

    def bulk_update_channel(self) -> None:
        channels = list_channels()
        if not channels:
            self._notify("Güncellenecek kanal bulunamadı.", error=True)
            return
        channel, accepted = QInputDialog.getItem(
            self,
            "Toplu Kanal Güncelle",
            "Yeni kanal:",
            channels,
            0,
            False,
        )
        if not accepted or not channel:
            return
        self._apply_bulk_action(
            "Toplu Kanal Güncelle",
            lambda action: update_action(action.id, {"channel": channel}),
        )

    def _notify(self, message: str, error: bool = False) -> None:
        box = QMessageBox.warning if error else QMessageBox.information
        box(self, "Bilgi", message)
