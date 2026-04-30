from __future__ import annotations

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

from crm_app.models import Opportunity
from crm_app.services.export_service import export_rows
from crm_app.services.contact_service import list_company_choices
from crm_app.services.offer_service import create_offer
from crm_app.services.opportunity_service import (
    create_opportunity,
    delete_opportunity,
    get_opportunity,
    list_opportunities,
    list_opportunity_currencies,
    list_opportunity_stages,
    update_opportunity,
)
from crm_app.ui.bulk_actions import (
    BulkDateDialog,
    confirm_bulk_action,
    create_bulk_action_controls,
    show_bulk_result,
    update_bulk_action_controls,
)
from crm_app.ui.offer_form import OfferFormDialog
from crm_app.ui.opportunity_form import OpportunityFormDialog
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


class OpportunitiesPage(QWidget):
    headers = [
        "Fırsat",
        "Şirket",
        "Kişi",
        "Aşama",
        "Beklenen Tutar",
        "Para Birimi",
        "Olasılık",
        "Tahmini Kapanış",
        "Not",
    ]
    export_headers = [
        "Fırsat",
        "Şirket",
        "Kişi",
        "Aşama",
        "Beklenen Tutar",
        "Para Birimi",
        "Olasılık",
        "Tahmini Kapanış",
        "Not",
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.opportunities: list[Opportunity] = []

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(12)

        root_layout.addWidget(
            create_page_header(
                "Fırsatlar",
                "Satış hattındaki fırsatları aşama, olasılık ve tutara göre yönetin.",
            )
        )

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Fırsat, şirket, kişi veya not içinde ara...")
        self.search_input.textChanged.connect(self.refresh_table)

        self.stage_filter = QComboBox()
        self.stage_filter.setMinimumWidth(155)
        self.stage_filter.currentIndexChanged.connect(self.refresh_table)

        self.company_filter = QComboBox()
        self.company_filter.setMinimumWidth(170)
        self.company_filter.currentIndexChanged.connect(self.refresh_table)

        self.currency_filter = QComboBox()
        self.currency_filter.setMinimumWidth(130)
        self.currency_filter.currentIndexChanged.connect(self.refresh_table)

        self.bulk_count_label, self.bulk_button = create_bulk_action_controls()
        self.bulk_menu = QMenu(self.bulk_button)
        self.bulk_menu.addAction("Toplu Aşama Güncelle", self.bulk_update_stage)
        self.bulk_menu.addAction("Toplu Olasılık Güncelle", self.bulk_update_probability)
        self.bulk_menu.addAction("Toplu Tahmini Kapanış Tarihi Güncelle", self.bulk_update_expected_close_date)
        self.bulk_button.setMenu(self.bulk_menu)

        add_button = QPushButton("Yeni Fırsat")
        create_offer_button = QPushButton("Teklif Oluştur")
        views_button = QPushButton("Görünümler")
        columns_button = QPushButton("Kolonlar")
        edit_button = QPushButton("Düzenle")
        delete_button = QPushButton("Sil")
        refresh_button = QPushButton("Yenile")
        export_button = QPushButton("Dışa Aktar")

        set_button_role(add_button, "primary")
        set_button_role(create_offer_button, "secondary")
        set_button_role(views_button, "ghost")
        set_button_role(columns_button, "ghost")
        set_button_role(edit_button, "secondary")
        set_button_role(delete_button, "danger")
        set_button_role(refresh_button, "ghost")
        set_button_role(export_button, "ghost")

        add_button.clicked.connect(self.add_opportunity)
        create_offer_button.clicked.connect(self.create_offer_from_selected_opportunity)
        edit_button.clicked.connect(self.edit_selected_opportunity)
        delete_button.clicked.connect(self.delete_selected_opportunity)
        refresh_button.clicked.connect(self.refresh_table)
        export_button.clicked.connect(self.export_opportunities_file)

        toolbar_card = create_list_page_toolbar(
            "Fırsat Listesi",
            "Arama, filtreleme ve fırsat kayıt işlemleri",
            top_actions=[
                add_button,
                create_offer_button,
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
            filter_widgets=[self.stage_filter, self.company_filter, self.currency_filter],
        )

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemDoubleClicked.connect(self.edit_selected_opportunity)
        configure_table(self.table)
        self.table.itemSelectionChanged.connect(self._update_bulk_actions_state)
        self.preferences = ListPagePreferences(
            "opportunities",
            self.table,
            filter_widgets={
                "search": self.search_input,
                "stage": self.stage_filter,
                "company": self.company_filter,
                "currency": self.currency_filter,
            },
            default_visible_columns=list(range(len(self.headers))),
            reset_callback=self.refresh_table,
        )
        self.preferences.attach_button(columns_button)
        self.preferences.attach_view_button(
            views_button,
            built_in_views={
                "Teklif Verildi": {
                    "filters": {
                        "search": {"kind": "line_edit", "text": ""},
                        "stage": {"kind": "combo_box", "data": "Teklif Verildi", "text": "Teklif Verildi"},
                        "company": {"kind": "combo_box", "data": None, "text": "Tüm Şirketler"},
                        "currency": {"kind": "combo_box", "data": "", "text": "Tüm Para Birimleri"},
                    }
                }
            },
        )

        table_card = create_list_table_card(self.table)

        root_layout.addWidget(toolbar_card)
        root_layout.addWidget(table_card, 1)

        self.refresh_filter_options()
        self.preferences.restore()
        self.refresh_table()

    def refresh_filter_options(self) -> None:
        current_stage = self.stage_filter.currentData()
        current_company = self.company_filter.currentData()
        current_currency = self.currency_filter.currentData()

        self.stage_filter.blockSignals(True)
        self.company_filter.blockSignals(True)
        self.currency_filter.blockSignals(True)

        self.stage_filter.clear()
        self.stage_filter.addItem("Tüm Aşamalar", "")
        for stage in list_opportunity_stages():
            self.stage_filter.addItem(stage, stage)

        self.company_filter.clear()
        self.company_filter.addItem("Tüm Şirketler", None)
        for company in list_company_choices():
            self.company_filter.addItem(company.name, company.id)

        self.currency_filter.clear()
        self.currency_filter.addItem("Tüm Para Birimleri", "")
        for currency in list_opportunity_currencies():
            self.currency_filter.addItem(currency, currency)

        self._restore_filter(self.stage_filter, current_stage)
        self._restore_filter(self.company_filter, current_company)
        self._restore_filter(self.currency_filter, current_currency)

        self.stage_filter.blockSignals(False)
        self.company_filter.blockSignals(False)
        self.currency_filter.blockSignals(False)

    def _restore_filter(self, widget: QComboBox, value: object) -> None:
        index = widget.findData(value)
        if index >= 0:
            widget.setCurrentIndex(index)

    def refresh_table(self) -> None:
        self.refresh_filter_options()
        self.opportunities = list_opportunities(
            search_text=self.search_input.text().strip(),
            stage=self.stage_filter.currentData() or "",
            company_id=self.company_filter.currentData(),
            currency=self.currency_filter.currentData() or "",
        )
        self.table.setRowCount(len(self.opportunities))

        if not self.opportunities:
            set_table_empty_state(
                self.table,
                "Arama ve filtrelere uygun fırsat kaydı bulunamadı.",
                action_label="Yeni Fırsat",
                action_handler=self.add_opportunity,
            )
            self.preferences.finalize_table_state()
            self._update_bulk_actions_state()
            return

        primary_font = QFont("Segoe UI", 9)
        primary_font.setBold(True)
        for row, opportunity in enumerate(self.opportunities):
            values = [
                opportunity.title,
                opportunity.company.name if opportunity.company else "-",
                opportunity.contact.name if opportunity.contact else "-",
                opportunity.stage,
                f"{opportunity.expected_amount:,.2f}",
                opportunity.currency or "-",
                f"{opportunity.probability}%",
                opportunity.expected_close_date.strftime("%d.%m.%Y") if opportunity.expected_close_date else "-",
                shorten(opportunity.note or "-", width=42, placeholder="..."),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                if column in {0, 3}:
                    item.setFont(primary_font)
                    item.setForeground(QColor("#11243a"))
                elif column in {1, 2, 5, 6, 7, 8}:
                    item.setForeground(QColor("#5f7188"))
                if column == 0:
                    set_row_identifier(item, opportunity.id)
                self.table.setItem(row, column, item)

        self.table.resizeColumnsToContents()
        self.preferences.finalize_table_state()
        self._update_bulk_actions_state()

    def add_opportunity(self) -> None:
        dialog = OpportunityFormDialog(parent=self)
        if dialog.exec():
            create_opportunity(dialog.get_data())
            self.refresh_table()
            self._notify("Fırsat kaydı oluşturuldu.")

    def export_opportunities_file(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Fırsatları Dışa Aktar",
            get_default_export_path("firsatlar.csv"),
            "CSV Dosyaları (*.csv);;Excel Dosyaları (*.xlsx)",
        )
        if not file_path:
            return

        rows = [
            [
                opportunity.title,
                opportunity.company.name if opportunity.company else "",
                opportunity.contact.name if opportunity.contact else "",
                opportunity.stage or "",
                f"{opportunity.expected_amount:,.2f}",
                opportunity.currency or "",
                opportunity.probability,
                opportunity.expected_close_date.strftime("%d.%m.%Y")
                if opportunity.expected_close_date
                else "",
                opportunity.note or "",
            ]
            for opportunity in self.opportunities
        ]
        export_rows(file_path, self.export_headers, rows)
        self._notify("Fırsat listesi dışa aktarıldı.")

    def edit_selected_opportunity(self, _item: QTableWidgetItem | None = None) -> None:
        opportunity = self._get_selected_opportunity()
        if not opportunity:
            self._notify("Lütfen bir fırsat seçin.", error=True)
            return

        fresh_opportunity = get_opportunity(opportunity.id)
        if not fresh_opportunity:
            self._notify("Fırsat kaydı bulunamadı.", error=True)
            return

        dialog = OpportunityFormDialog(opportunity=fresh_opportunity, parent=self)
        if dialog.exec():
            update_opportunity(fresh_opportunity.id, dialog.get_data())
            self.refresh_table()
            self._notify("Fırsat kaydı güncellendi.")

    def delete_selected_opportunity(self) -> None:
        opportunity = self._get_selected_opportunity()
        if not opportunity:
            self._notify("Lütfen bir fırsat seçin.", error=True)
            return

        answer = QMessageBox.question(
            self,
            "Fırsat Sil",
            f"{opportunity.title} kaydını silmek istiyor musunuz?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            delete_opportunity(opportunity.id)
            self.refresh_table()
            self._notify("Fırsat kaydı silindi.")

    def _get_selected_opportunity(self) -> Opportunity | None:
        selected_ids = get_selected_row_identifiers(self.table)
        if len(selected_ids) != 1:
            return None
        opportunity_id = selected_ids[0]
        if opportunity_id is None:
            return None
        return next(
            (opportunity for opportunity in self.opportunities if opportunity.id == opportunity_id),
            None,
        )

    def _get_selected_opportunities(self) -> list[Opportunity]:
        selected_ids = get_selected_row_identifiers(self.table)
        selected_map = {opportunity.id: opportunity for opportunity in self.opportunities}
        return [
            selected_map[opportunity_id]
            for opportunity_id in selected_ids
            if opportunity_id in selected_map
        ]

    def _update_bulk_actions_state(self) -> None:
        update_bulk_action_controls(self.bulk_count_label, self.bulk_button, len(self._get_selected_opportunities()))

    def bulk_update_stage(self) -> None:
        opportunities = self._get_selected_opportunities()
        if len(opportunities) < 2:
            self._notify("Toplu işlem için en az iki fırsat seçin.", error=True)
            return

        stages = list_opportunity_stages()
        stage, accepted = QInputDialog.getItem(
            self,
            "Toplu Aşama Güncelle",
            "Yeni aşama:",
            stages,
            0,
            False,
        )
        if not accepted or not stage:
            return
        if not confirm_bulk_action(self, "Toplu Aşama Güncelle", len(opportunities)):
            return

        success_count = 0
        failures: list[str] = []
        for opportunity in opportunities:
            try:
                update_opportunity(opportunity.id, {"stage": stage})
                success_count += 1
            except Exception as exc:
                failures.append(f"{opportunity.title}: {exc}")

        self.refresh_table()
        show_bulk_result(self, success_count=success_count, failures=failures)

    def bulk_update_probability(self) -> None:
        opportunities = self._get_selected_opportunities()
        if len(opportunities) < 2:
            self._notify("Toplu işlem için en az iki fırsat seçin.", error=True)
            return

        probability, accepted = QInputDialog.getInt(
            self,
            "Toplu Olasılık Güncelle",
            "Yeni olasılık (%):",
            value=50,
            minValue=0,
            maxValue=100,
        )
        if not accepted:
            return
        if not confirm_bulk_action(self, "Toplu Olasılık Güncelle", len(opportunities)):
            return

        success_count = 0
        failures: list[str] = []
        for opportunity in opportunities:
            try:
                update_opportunity(opportunity.id, {"probability": probability})
                success_count += 1
            except Exception as exc:
                failures.append(f"{opportunity.title}: {exc}")

        self.refresh_table()
        show_bulk_result(self, success_count=success_count, failures=failures)

    def bulk_update_expected_close_date(self) -> None:
        opportunities = self._get_selected_opportunities()
        if len(opportunities) < 2:
            self._notify("Toplu işlem için en az iki fırsat seçin.", error=True)
            return

        dialog = BulkDateDialog("Toplu Tahmini Kapanış Tarihi", "Tahmini kapanış tarihi:", self)
        if not dialog.exec():
            return
        target_date = dialog.get_value()
        if not confirm_bulk_action(self, "Toplu Tahmini Kapanış Tarihi Güncelle", len(opportunities)):
            return

        success_count = 0
        failures: list[str] = []
        for opportunity in opportunities:
            try:
                update_opportunity(opportunity.id, {"expected_close_date": target_date})
                success_count += 1
            except Exception as exc:
                failures.append(f"{opportunity.title}: {exc}")

        self.refresh_table()
        show_bulk_result(self, success_count=success_count, failures=failures)

    def create_offer_from_selected_opportunity(self) -> None:
        opportunity = self._get_selected_opportunity()
        if not opportunity:
            self._notify("Lütfen bir fırsat seçin.", error=True)
            return

        note = f"Fırsat kaynağı: {opportunity.title}"
        if opportunity.note:
            note = f"{note}\n{opportunity.note}"

        dialog = OfferFormDialog(
            initial_company_id=opportunity.company_id,
            initial_contact_id=opportunity.contact_id,
            initial_description=opportunity.title,
            initial_amount=float(opportunity.expected_amount or 0),
            initial_currency=opportunity.currency or "EUR",
            initial_note=note,
            parent=self,
        )
        if dialog.exec():
            create_offer(dialog.get_data())
            self._notify("Seçili fırsattan teklif oluşturuldu.")

    def _notify(self, message: str, error: bool = False) -> None:
        box = QMessageBox.warning if error else QMessageBox.information
        box(self, "Bilgi", message)
