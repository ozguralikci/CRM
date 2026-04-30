from __future__ import annotations

from datetime import date, timedelta
from textwrap import shorten

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
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

from crm_app.models import Sample
from crm_app.services.action_service import create_action
from crm_app.services.export_service import export_rows
from crm_app.services.contact_service import list_company_choices
from crm_app.services.opportunity_service import create_opportunity
from crm_app.services.sample_service import (
    create_sample,
    delete_sample,
    get_sample,
    list_sample_statuses,
    list_samples,
    update_sample,
)
from crm_app.ui.action_form import ActionFormDialog
from crm_app.ui.bulk_actions import (
    BulkDateDialog,
    confirm_bulk_action,
    create_bulk_action_controls,
    show_bulk_result,
    update_bulk_action_controls,
)
from crm_app.ui.opportunity_form import OpportunityFormDialog
from crm_app.ui.sample_form import SampleFormDialog
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


class SamplesPage(QWidget):
    headers = ["Şirket", "Kişi", "Ürün", "Adet", "Gönderim Tarihi", "Durum", "Not"]
    export_headers = ["Şirket", "Kişi", "Ürün", "Adet", "Gönderim Tarihi", "Durum", "Not"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.samples: list[Sample] = []

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(12)

        root_layout.addWidget(
            create_page_header(
                "Numuneler",
                "Numune gönderimlerini, durumlarını ve geri dönüşlerini tek ekranda takip edin.",
            )
        )

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Şirket, kişi, ürün veya not içinde ara...")
        self.search_input.textChanged.connect(self.refresh_table)

        self.status_filter = QComboBox()
        self.status_filter.setMinimumWidth(150)
        self.status_filter.currentIndexChanged.connect(self.refresh_table)

        self.company_filter = QComboBox()
        self.company_filter.setMinimumWidth(170)
        self.company_filter.currentIndexChanged.connect(self.refresh_table)

        self.bulk_count_label, self.bulk_button = create_bulk_action_controls()
        self.bulk_menu = QMenu(self.bulk_button)
        self.bulk_menu.addAction("Toplu Durum Güncelle", self.bulk_update_status)
        self.bulk_menu.addAction("Toplu Gönderim Tarihi Güncelle", self.bulk_update_sent_date)
        self.bulk_button.setMenu(self.bulk_menu)

        add_button = QPushButton("Yeni Numune")
        follow_up_button = QPushButton("Takip Aksiyonu Oluştur")
        views_button = QPushButton("Görünümler")
        columns_button = QPushButton("Kolonlar")
        edit_button = QPushButton("Düzenle")
        delete_button = QPushButton("Sil")
        refresh_button = QPushButton("Yenile")
        export_button = QPushButton("Dışa Aktar")

        set_button_role(add_button, "primary")
        set_button_role(follow_up_button, "secondary")
        set_button_role(views_button, "ghost")
        set_button_role(columns_button, "ghost")
        set_button_role(edit_button, "secondary")
        set_button_role(delete_button, "danger")
        set_button_role(refresh_button, "ghost")
        set_button_role(export_button, "ghost")

        add_button.clicked.connect(self.add_sample)
        follow_up_button.clicked.connect(self.create_follow_up_action_for_selected_sample)
        edit_button.clicked.connect(self.edit_selected_sample)
        delete_button.clicked.connect(self.delete_selected_sample)
        refresh_button.clicked.connect(self.refresh_table)
        export_button.clicked.connect(self.export_samples_file)

        toolbar_card = create_list_page_toolbar(
            "Numune Listesi",
            "Arama, filtreleme ve numune kayıt işlemleri",
            top_actions=[
                add_button,
                follow_up_button,
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
            filter_widgets=[self.status_filter, self.company_filter],
        )

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemDoubleClicked.connect(self.edit_selected_sample)
        configure_table(self.table)
        self.table.itemSelectionChanged.connect(self._update_bulk_actions_state)
        self.preferences = ListPagePreferences(
            "samples",
            self.table,
            filter_widgets={
                "search": self.search_input,
                "status": self.status_filter,
                "company": self.company_filter,
            },
            default_visible_columns=list(range(len(self.headers))),
            reset_callback=self.refresh_table,
        )
        self.preferences.attach_button(columns_button)
        self.preferences.attach_view_button(
            views_button,
            built_in_views={
                "Testte Olanlar": {
                    "filters": {
                        "search": {"kind": "line_edit", "text": ""},
                        "status": {"kind": "combo_box", "data": "Testte", "text": "Testte"},
                        "company": {"kind": "combo_box", "data": None, "text": "Tüm Şirketler"},
                    }
                },
                "Olumlu Dönenler": {
                    "filters": {
                        "search": {"kind": "line_edit", "text": ""},
                        "status": {"kind": "combo_box", "data": "Olumlu", "text": "Olumlu"},
                        "company": {"kind": "combo_box", "data": None, "text": "Tüm Şirketler"},
                    }
                },
            },
        )

        table_card = create_list_table_card(self.table)

        root_layout.addWidget(toolbar_card)
        root_layout.addWidget(table_card, 1)

        self.refresh_filter_options()
        self.preferences.restore()
        self.refresh_table()

    def refresh_filter_options(self) -> None:
        current_status = self.status_filter.currentData()
        current_company = self.company_filter.currentData()

        self.status_filter.blockSignals(True)
        self.company_filter.blockSignals(True)

        self.status_filter.clear()
        self.status_filter.addItem("Tüm Durumlar", "")
        for status in list_sample_statuses():
            self.status_filter.addItem(status, status)

        self.company_filter.clear()
        self.company_filter.addItem("Tüm Şirketler", None)
        for company in list_company_choices():
            self.company_filter.addItem(company.name, company.id)

        self._restore_filter(self.status_filter, current_status)
        self._restore_filter(self.company_filter, current_company)

        self.status_filter.blockSignals(False)
        self.company_filter.blockSignals(False)

    def _restore_filter(self, widget: QComboBox, value: object) -> None:
        index = widget.findData(value)
        if index >= 0:
            widget.setCurrentIndex(index)

    def refresh_table(self) -> None:
        self.refresh_filter_options()
        self.samples = list_samples(
            search_text=self.search_input.text().strip(),
            status=self.status_filter.currentData() or "",
            company_id=self.company_filter.currentData(),
        )
        self.table.setRowCount(len(self.samples))

        if not self.samples:
            set_table_empty_state(
                self.table,
                "Arama ve filtrelere uygun numune kaydı bulunamadı.",
                action_label="Yeni Numune",
                action_handler=self.add_sample,
            )
            self.preferences.finalize_table_state()
            self._update_bulk_actions_state()
            return

        primary_font = QFont("Segoe UI", 9)
        primary_font.setBold(True)
        for row, sample in enumerate(self.samples):
            values = [
                sample.company.name if sample.company else "-",
                sample.contact.name if sample.contact else "-",
                sample.product or "-",
                str(sample.quantity),
                sample.sent_date.strftime("%d.%m.%Y") if sample.sent_date else "-",
                sample.status or "-",
                shorten(sample.note or "-", width=40, placeholder="..."),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                if column in {0, 2}:
                    item.setFont(primary_font)
                    item.setForeground(QColor("#11243a"))
                elif column in {1, 4, 5, 6}:
                    item.setForeground(QColor("#5f7188"))
                if column == 0:
                    set_row_identifier(item, sample.id)
                self.table.setItem(row, column, item)

        self.table.resizeColumnsToContents()
        self.preferences.finalize_table_state()
        self._update_bulk_actions_state()

    def add_sample(self) -> None:
        dialog = SampleFormDialog(parent=self)
        if dialog.exec():
            sample = create_sample(dialog.get_data())
            self.refresh_table()
            self._notify("Numune kaydı oluşturuldu.")
            self._handle_sample_workflow_suggestions(sample, previous_status=None)

    def export_samples_file(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Numuneleri Dışa Aktar",
            get_default_export_path("numuneler.csv"),
            "CSV Dosyaları (*.csv);;Excel Dosyaları (*.xlsx)",
        )
        if not file_path:
            return

        rows = [
            [
                sample.company.name if sample.company else "",
                sample.contact.name if sample.contact else "",
                sample.product or "",
                sample.quantity,
                sample.sent_date.strftime("%d.%m.%Y") if sample.sent_date else "",
                sample.status or "",
                sample.note or "",
            ]
            for sample in self.samples
        ]
        export_rows(file_path, self.export_headers, rows)
        self._notify("Numune listesi dışa aktarıldı.")

    def edit_selected_sample(self, _item: QTableWidgetItem | None = None) -> None:
        sample = self._get_selected_sample()
        if not sample:
            self._notify("Lütfen bir numune seçin.", error=True)
            return

        fresh_sample = get_sample(sample.id)
        if not fresh_sample:
            self._notify("Numune kaydı bulunamadı.", error=True)
            return

        dialog = SampleFormDialog(sample=fresh_sample, parent=self)
        if dialog.exec():
            previous_status = fresh_sample.status or ""
            update_sample(fresh_sample.id, dialog.get_data())
            updated_sample = get_sample(fresh_sample.id)
            self.refresh_table()
            self._notify("Numune kaydı güncellendi.")
            if updated_sample:
                self._handle_sample_workflow_suggestions(updated_sample, previous_status=previous_status)

    def delete_selected_sample(self) -> None:
        sample = self._get_selected_sample()
        if not sample:
            self._notify("Lütfen bir numune seçin.", error=True)
            return

        answer = QMessageBox.question(
            self,
            "Numune Sil",
            f"{sample.product} kaydını silmek istiyor musunuz?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            delete_sample(sample.id)
            self.refresh_table()
            self._notify("Numune kaydı silindi.")

    def _get_selected_sample(self) -> Sample | None:
        selected_ids = get_selected_row_identifiers(self.table)
        if len(selected_ids) != 1:
            return None
        sample_id = selected_ids[0]
        if sample_id is None:
            return None
        return next((sample for sample in self.samples if sample.id == sample_id), None)

    def _get_selected_samples(self) -> list[Sample]:
        selected_ids = get_selected_row_identifiers(self.table)
        selected_map = {sample.id: sample for sample in self.samples}
        return [selected_map[sample_id] for sample_id in selected_ids if sample_id in selected_map]

    def _update_bulk_actions_state(self) -> None:
        update_bulk_action_controls(self.bulk_count_label, self.bulk_button, len(self._get_selected_samples()))

    def bulk_update_status(self) -> None:
        samples = self._get_selected_samples()
        if len(samples) < 2:
            self._notify("Toplu işlem için en az iki numune seçin.", error=True)
            return

        statuses = list_sample_statuses()
        status, accepted = QInputDialog.getItem(
            self,
            "Toplu Durum Güncelle",
            "Yeni durum:",
            statuses,
            0,
            False,
        )
        if not accepted or not status:
            return
        if not confirm_bulk_action(self, "Toplu Durum Güncelle", len(samples)):
            return

        success_count = 0
        failures: list[str] = []
        for sample in samples:
            try:
                update_sample(sample.id, {"status": status})
                success_count += 1
            except Exception as exc:
                failures.append(f"{sample.product or sample.id}: {exc}")

        self.refresh_table()
        show_bulk_result(self, success_count=success_count, failures=failures)

    def bulk_update_sent_date(self) -> None:
        samples = self._get_selected_samples()
        if len(samples) < 2:
            self._notify("Toplu işlem için en az iki numune seçin.", error=True)
            return

        dialog = BulkDateDialog("Toplu Gönderim Tarihi", "Gönderim tarihi:", self)
        if not dialog.exec():
            return
        sent_date = dialog.get_value()
        if not confirm_bulk_action(self, "Toplu Gönderim Tarihi Güncelle", len(samples)):
            return

        success_count = 0
        failures: list[str] = []
        for sample in samples:
            try:
                update_sample(sample.id, {"sent_date": sent_date})
                success_count += 1
            except Exception as exc:
                failures.append(f"{sample.product or sample.id}: {exc}")

        self.refresh_table()
        show_bulk_result(self, success_count=success_count, failures=failures)

    def create_follow_up_action_for_selected_sample(self) -> None:
        sample = self._get_selected_sample()
        if not sample:
            self._notify("Lütfen bir numune seçin.", error=True)
            return
        self._open_follow_up_action_dialog(sample)

    def _open_follow_up_action_dialog(self, sample: Sample, *, next_action: str | None = None) -> None:
        follow_up_text = next_action or "Numune geri bildirimini al"
        summary_note = (
            f"Ürün: {sample.product or '-'}\n"
            f"Durum: {sample.status or '-'}\n"
            f"Adet: {sample.quantity}"
        )
        if sample.note:
            summary_note = f"{summary_note}\nNot: {sample.note}"

        dialog = ActionFormDialog(
            initial_company_id=sample.company_id,
            initial_contact_id=sample.contact_id,
            initial_record_type="Kisi" if sample.contact_id else "Sirket",
            initial_action_type="Numune Takibi",
            initial_channel="Telefon",
            initial_note=summary_note,
            initial_next_action=follow_up_text,
            initial_next_action_date=date.today() + timedelta(days=2),
            parent=self,
        )
        if dialog.exec():
            create_action(dialog.get_data())
            self._notify("Numune için takip aksiyonu oluşturuldu.")

    def _handle_sample_workflow_suggestions(
        self,
        sample: Sample,
        previous_status: str | None,
    ) -> None:
        current_status = sample.status or ""
        if current_status == previous_status:
            return

        if current_status == "Olumlu":
            box = QMessageBox(self)
            box.setWindowTitle("Workflow Önerisi")
            box.setIcon(QMessageBox.Icon.Information)
            box.setText(
                "Numune sonucu olumlu görünüyor. İsterseniz hemen takip aksiyonu oluşturabilir veya fırsat açabilirsiniz."
            )
            action_button = box.addButton("Takip Aksiyonu Oluştur", QMessageBox.ButtonRole.AcceptRole)
            opportunity_button = box.addButton("Fırsat Oluştur", QMessageBox.ButtonRole.ActionRole)
            box.addButton("Daha Sonra", QMessageBox.ButtonRole.RejectRole)
            box.exec()
            clicked = box.clickedButton()
            if clicked == action_button:
                self._open_follow_up_action_dialog(sample, next_action="Olumlu numune sonucunu fırsata çevir")
            elif clicked == opportunity_button:
                title = f"{sample.product} fırsatı" if sample.product else "Yeni fırsat"
                note = "Olumlu numune geri bildirimi alındı."
                if sample.note:
                    note = f"{note}\n{sample.note}"
                dialog = OpportunityFormDialog(
                    initial_company_id=sample.company_id,
                    initial_contact_id=sample.contact_id,
                    initial_title=title,
                    initial_note=note,
                    initial_stage="Numune Gönderildi",
                    parent=self,
                )
                if dialog.exec():
                    create_opportunity(dialog.get_data())
                    self._notify("Olumlu numuneden yeni fırsat oluşturuldu.")
            return

        if current_status == "Olumsuz":
            answer = QMessageBox.question(
                self,
                "Workflow Önerisi",
                "Numune sonucu olumsuz kaydedildi. Değerlendirme için bir takip aksiyonu oluşturmak ister misiniz?",
            )
            if answer == QMessageBox.StandardButton.Yes:
                self._open_follow_up_action_dialog(sample, next_action="Olumsuz numune geri bildirimini değerlendir")

    def _notify(self, message: str, error: bool = False) -> None:
        box = QMessageBox.warning if error else QMessageBox.information
        box(self, "Bilgi", message)
