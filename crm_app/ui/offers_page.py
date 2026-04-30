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

from crm_app.models import Offer
from crm_app.services.action_service import create_action
from crm_app.services.export_service import export_rows
from crm_app.services.contact_service import list_company_choices
from crm_app.services.offer_service import (
    create_offer,
    delete_offer,
    get_offer,
    list_offer_currencies,
    list_offer_statuses,
    list_offers,
    split_offer_note,
    update_offer,
)
from crm_app.services.opportunity_service import find_related_open_opportunity, update_opportunity
from crm_app.ui.action_form import ActionFormDialog
from crm_app.ui.bulk_actions import (
    confirm_bulk_action,
    create_bulk_action_controls,
    show_bulk_result,
    update_bulk_action_controls,
)
from crm_app.ui.offer_form import OfferFormDialog
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


class OffersPage(QWidget):
    headers = [
        "Teklif No",
        "Şirket",
        "Kişi",
        "Tarih",
        "Ürün / Açıklama",
        "Tutar",
        "Para Birimi",
        "Durum",
        "Dosya",
        "Not",
    ]
    export_headers = [
        "Teklif No",
        "Şirket",
        "Kişi",
        "Tarih",
        "Ürün / Açıklama",
        "Tutar",
        "Para Birimi",
        "Durum",
        "Dosya",
        "Not",
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.offers: list[Offer] = []

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(12)

        root_layout.addWidget(
            create_page_header(
                "Teklifler",
                "Teklif sürecini, tutarları ve durumları tek ekranda takip edin.",
            )
        )

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Teklif no, not veya dosya yolunda ara...")
        self.search_input.textChanged.connect(self.refresh_table)

        self.status_filter = QComboBox()
        self.status_filter.setMinimumWidth(140)
        self.status_filter.currentIndexChanged.connect(self.refresh_table)

        self.currency_filter = QComboBox()
        self.currency_filter.setMinimumWidth(130)
        self.currency_filter.currentIndexChanged.connect(self.refresh_table)

        self.company_filter = QComboBox()
        self.company_filter.setMinimumWidth(160)
        self.company_filter.currentIndexChanged.connect(self.refresh_table)

        self.bulk_count_label, self.bulk_button = create_bulk_action_controls()
        self.bulk_menu = QMenu(self.bulk_button)
        self.bulk_menu.addAction("Toplu Durum Güncelle", self.bulk_update_status)
        self.bulk_button.setMenu(self.bulk_menu)

        add_button = QPushButton("Yeni Teklif")
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

        add_button.clicked.connect(self.add_offer)
        follow_up_button.clicked.connect(self.create_follow_up_action_for_selected_offer)
        edit_button.clicked.connect(self.edit_selected_offer)
        delete_button.clicked.connect(self.delete_selected_offer)
        refresh_button.clicked.connect(self.refresh_table)
        export_button.clicked.connect(self.export_offers_file)

        toolbar_card = create_list_page_toolbar(
            "Teklif Listesi",
            "Arama, filtreleme ve teklif kayıt işlemleri",
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
            filter_widgets=[self.status_filter, self.currency_filter, self.company_filter],
        )

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemDoubleClicked.connect(self.edit_selected_offer)
        configure_table(self.table)
        self.table.itemSelectionChanged.connect(self._update_bulk_actions_state)
        self.preferences = ListPagePreferences(
            "offers",
            self.table,
            filter_widgets={
                "search": self.search_input,
                "status": self.status_filter,
                "currency": self.currency_filter,
                "company": self.company_filter,
            },
            default_visible_columns=list(range(len(self.headers))),
            reset_callback=self.refresh_table,
        )
        self.preferences.attach_button(columns_button)
        self.preferences.attach_view_button(
            views_button,
            built_in_views={
                "Kabul Edilenler": {
                    "filters": {
                        "search": {"kind": "line_edit", "text": ""},
                        "status": {"kind": "combo_box", "data": "Kabul Edildi", "text": "Kabul Edildi"},
                        "currency": {"kind": "combo_box", "data": "", "text": "Tüm Para Birimleri"},
                        "company": {"kind": "combo_box", "data": None, "text": "Tüm Şirketler"},
                    }
                },
                "Reddedilenler": {
                    "filters": {
                        "search": {"kind": "line_edit", "text": ""},
                        "status": {"kind": "combo_box", "data": "Reddedildi", "text": "Reddedildi"},
                        "currency": {"kind": "combo_box", "data": "", "text": "Tüm Para Birimleri"},
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
        current_currency = self.currency_filter.currentData()
        current_company = self.company_filter.currentData()

        self.status_filter.blockSignals(True)
        self.currency_filter.blockSignals(True)
        self.company_filter.blockSignals(True)

        self.status_filter.clear()
        self.status_filter.addItem("Tüm Durumlar", "")
        for status in list_offer_statuses():
            self.status_filter.addItem(status, status)

        self.currency_filter.clear()
        self.currency_filter.addItem("Tüm Para Birimleri", "")
        for currency in list_offer_currencies():
            self.currency_filter.addItem(currency, currency)

        self.company_filter.clear()
        self.company_filter.addItem("Tüm Şirketler", None)
        for company in list_company_choices():
            self.company_filter.addItem(company.name, company.id)

        self._restore_filter(self.status_filter, current_status)
        self._restore_filter(self.currency_filter, current_currency)
        self._restore_filter(self.company_filter, current_company)

        self.status_filter.blockSignals(False)
        self.currency_filter.blockSignals(False)
        self.company_filter.blockSignals(False)

    def _restore_filter(self, widget: QComboBox, value: object) -> None:
        index = widget.findData(value)
        if index >= 0:
            widget.setCurrentIndex(index)

    def refresh_table(self) -> None:
        self.refresh_filter_options()
        self.offers = list_offers(
            search_text=self.search_input.text().strip(),
            status=self.status_filter.currentData() or "",
            currency=self.currency_filter.currentData() or "",
            company_id=self.company_filter.currentData(),
        )
        self.table.setRowCount(len(self.offers))

        if not self.offers:
            set_table_empty_state(
                self.table,
                "Arama ve filtrelere uygun teklif kaydı bulunamadı.",
                action_label="Yeni Teklif",
                action_handler=self.add_offer,
            )
            self.preferences.finalize_table_state()
            self._update_bulk_actions_state()
            return

        primary_font = QFont("Segoe UI", 9)
        primary_font.setBold(True)
        for row, offer in enumerate(self.offers):
            description, details = split_offer_note(offer.note or "")
            values = [
                offer.offer_no,
                offer.company.name if offer.company else "-",
                offer.contact.name if offer.contact else "-",
                offer.date.strftime("%d.%m.%Y") if offer.date else "-",
                shorten(description or "-", width=30, placeholder="..."),
                f"{offer.amount:,.2f}",
                offer.currency or "-",
                offer.status or "-",
                shorten(offer.file_path or "-", width=24, placeholder="..."),
                shorten(details or "-", width=28, placeholder="..."),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                if column in {0, 1}:
                    item.setFont(primary_font)
                    item.setForeground(QColor("#11243a"))
                elif column in {3, 6, 7, 8, 9}:
                    item.setForeground(QColor("#5f7188"))
                if column == 0:
                    set_row_identifier(item, offer.id)
                self.table.setItem(row, column, item)

        self.table.resizeColumnsToContents()
        self.preferences.finalize_table_state()
        self._update_bulk_actions_state()

    def add_offer(self) -> None:
        dialog = OfferFormDialog(parent=self)
        if dialog.exec():
            offer = create_offer(dialog.get_data())
            self.refresh_table()
            self._notify("Teklif kaydı oluşturuldu.")
            self._handle_offer_workflow_suggestions(offer, previous_status=None)

    def export_offers_file(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Teklifleri Dışa Aktar",
            get_default_export_path("teklifler.csv"),
            "CSV Dosyaları (*.csv);;Excel Dosyaları (*.xlsx)",
        )
        if not file_path:
            return

        rows = []
        for offer in self.offers:
            description, details = split_offer_note(offer.note or "")
            rows.append(
                [
                    offer.offer_no,
                    offer.company.name if offer.company else "",
                    offer.contact.name if offer.contact else "",
                    offer.date.strftime("%d.%m.%Y") if offer.date else "",
                    description,
                    f"{offer.amount:,.2f}",
                    offer.currency or "",
                    offer.status or "",
                    offer.file_path or "",
                    details,
                ]
            )

        export_rows(file_path, self.export_headers, rows)
        self._notify("Teklif listesi dışa aktarıldı.")

    def edit_selected_offer(self, _item: QTableWidgetItem | None = None) -> None:
        offer = self._get_selected_offer()
        if not offer:
            self._notify("Lütfen bir teklif seçin.", error=True)
            return

        fresh_offer = get_offer(offer.id)
        if not fresh_offer:
            self._notify("Teklif kaydı bulunamadı.", error=True)
            return

        dialog = OfferFormDialog(offer=fresh_offer, parent=self)
        if dialog.exec():
            previous_status = fresh_offer.status or ""
            update_offer(fresh_offer.id, dialog.get_data())
            updated_offer = get_offer(fresh_offer.id)
            self.refresh_table()
            self._notify("Teklif kaydı güncellendi.")
            if updated_offer:
                self._handle_offer_workflow_suggestions(updated_offer, previous_status=previous_status)

    def delete_selected_offer(self) -> None:
        offer = self._get_selected_offer()
        if not offer:
            self._notify("Lütfen bir teklif seçin.", error=True)
            return

        answer = QMessageBox.question(
            self,
            "Teklif Sil",
            f"{offer.offer_no} kaydını silmek istiyor musunuz?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            delete_offer(offer.id)
            self.refresh_table()
            self._notify("Teklif kaydı silindi.")

    def _get_selected_offer(self) -> Offer | None:
        selected_ids = get_selected_row_identifiers(self.table)
        if len(selected_ids) != 1:
            return None
        offer_id = selected_ids[0]
        if offer_id is None:
            return None
        return next((offer for offer in self.offers if offer.id == offer_id), None)

    def _get_selected_offers(self) -> list[Offer]:
        selected_ids = get_selected_row_identifiers(self.table)
        selected_map = {offer.id: offer for offer in self.offers}
        return [selected_map[offer_id] for offer_id in selected_ids if offer_id in selected_map]

    def _update_bulk_actions_state(self) -> None:
        update_bulk_action_controls(self.bulk_count_label, self.bulk_button, len(self._get_selected_offers()))

    def bulk_update_status(self) -> None:
        offers = self._get_selected_offers()
        if len(offers) < 2:
            self._notify("Toplu işlem için en az iki teklif seçin.", error=True)
            return

        statuses = list_offer_statuses()
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

        if status in {"Kabul Edildi", "Reddedildi"}:
            answer = QMessageBox.question(
                self,
                "Kritik Durum Güncellemesi",
                f"Seçili tekliflerin durumu '{status}' olarak güncellensin mi?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        if not confirm_bulk_action(self, "Toplu Durum Güncelle", len(offers)):
            return

        success_count = 0
        failures: list[str] = []
        for offer in offers:
            try:
                update_offer(offer.id, {"offer_no": offer.offer_no, "status": status})
                success_count += 1
            except Exception as exc:
                failures.append(f"{offer.offer_no}: {exc}")

        self.refresh_table()
        show_bulk_result(self, success_count=success_count, failures=failures)

    def create_follow_up_action_for_selected_offer(self) -> None:
        offer = self._get_selected_offer()
        if not offer:
            self._notify("Lütfen bir teklif seçin.", error=True)
            return
        self._open_follow_up_action_dialog(offer)

    def _open_follow_up_action_dialog(self, offer: Offer) -> None:
        description, details = split_offer_note(offer.note or "")
        summary_note = (
            f"Teklif No: {offer.offer_no}\n"
            f"Durum: {offer.status or '-'}\n"
            f"Ürün / Açıklama: {description or '-'}"
        )
        if details:
            summary_note = f"{summary_note}\nNot: {details}"

        dialog = ActionFormDialog(
            initial_company_id=offer.company_id,
            initial_contact_id=offer.contact_id,
            initial_record_type="Kisi" if offer.contact_id else "Sirket",
            initial_action_type="Teklif Takibi",
            initial_channel="Telefon",
            initial_note=summary_note,
            initial_next_action="Teklif geri dönüşünü al",
            initial_next_action_date=date.today() + timedelta(days=2),
            parent=self,
        )
        if dialog.exec():
            create_action(dialog.get_data())
            self._notify("Teklif takibi için aksiyon oluşturuldu.")

    def _handle_offer_workflow_suggestions(
        self,
        offer: Offer,
        previous_status: str | None,
    ) -> None:
        current_status = offer.status or ""
        if current_status != "Kabul Edildi" or previous_status == "Kabul Edildi":
            return

        related_opportunity = find_related_open_opportunity(offer.company_id, offer.contact_id)
        if not related_opportunity:
            return

        answer = QMessageBox.question(
            self,
            "Workflow Önerisi",
            (
                f"{offer.offer_no} teklifi kabul edildi. "
                f"İlişkili fırsat \"{related_opportunity.title}\" aşaması \"Kazanıldı\" olarak güncellensin mi?"
            ),
        )
        if answer == QMessageBox.StandardButton.Yes:
            update_opportunity(
                related_opportunity.id,
                {
                    "stage": "Kazanıldı",
                    "probability": 100,
                },
            )
            self._notify("İlişkili fırsat \"Kazanıldı\" aşamasına güncellendi.")

    def _notify(self, message: str, error: bool = False) -> None:
        box = QMessageBox.warning if error else QMessageBox.information
        box(self, "Bilgi", message)
