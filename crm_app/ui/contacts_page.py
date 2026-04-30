from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crm_app.models import Contact
from crm_app.services.action_service import create_action
from crm_app.services.export_service import export_rows
from crm_app.services.import_service import import_contacts
from crm_app.services.contact_service import (
    create_contact,
    delete_contact,
    get_contact,
    list_company_choices,
    list_contacts,
    update_contact,
)
from crm_app.services.field_service import get_field_values
from crm_app.ui.action_form import ActionFormDialog
from crm_app.ui.bulk_actions import (
    confirm_bulk_action,
    create_bulk_action_controls,
    show_bulk_result,
    update_bulk_action_controls,
)
from crm_app.ui.contact_form import ContactFormDialog
from crm_app.ui.contact_detail_dialog import ContactDetailDialog
from crm_app.ui.list_page_helpers import (
    create_list_page_toolbar,
    create_list_table_card,
    set_table_empty_state,
)
from crm_app.ui.list_preferences import (
    ListPagePreferences,
    get_selected_row_identifiers,
    set_row_identifier,
)
from crm_app.ui.styles import (
    configure_table,
    create_page_header,
    set_button_role,
)
from crm_app.utils.app_paths import get_default_export_path, get_default_import_dir


class ContactsPage(QWidget):
    headers = ["Ad Soyad", "Sirket", "Unvan", "Email", "Telefon"]
    export_headers = ["Ad Soyad", "Sirket", "Unvan", "Email", "Telefon"]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.contacts: list[Contact] = []

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)
        root_layout.setSpacing(12)

        root_layout.addWidget(
            create_page_header(
                "Kisiler",
                "Sirketlere bagli tum kisileri tek ekranda filtreleyin ve yonetin.",
            )
        )

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Ada gore kisi ara...")
        self.search_input.textChanged.connect(self.refresh_table)

        self.bulk_count_label, self.bulk_button = create_bulk_action_controls()
        self.bulk_menu = QMenu(self.bulk_button)
        self.bulk_menu.addAction("Toplu Şirket Ata", self.bulk_assign_company)
        self.bulk_button.setMenu(self.bulk_menu)

        add_button = QPushButton("Yeni Kisi")
        quick_action_button = QPushButton("Hızlı Aksiyon")
        self.detail_button = QPushButton("Detay")
        views_button = QPushButton("Görünümler")
        columns_button = QPushButton("Kolonlar")
        edit_button = QPushButton("Duzenle")
        delete_button = QPushButton("Sil")
        import_button = QPushButton("Ice Aktar")
        export_button = QPushButton("Disa Aktar")
        set_button_role(add_button, "primary")
        set_button_role(quick_action_button, "secondary")
        set_button_role(self.detail_button, "secondary")
        set_button_role(views_button, "ghost")
        set_button_role(columns_button, "ghost")
        set_button_role(edit_button, "secondary")
        set_button_role(delete_button, "danger")
        set_button_role(import_button, "ghost")
        set_button_role(export_button, "ghost")
        self.detail_button.setMinimumWidth(88)
        self.detail_button.setEnabled(False)

        add_button.clicked.connect(self.add_contact)
        quick_action_button.clicked.connect(self.quick_create_action)
        self.detail_button.clicked.connect(self.open_contact_detail)
        edit_button.clicked.connect(self.edit_selected_contact)
        delete_button.clicked.connect(self.delete_selected_contact)
        import_button.clicked.connect(self.import_contacts_file)
        export_button.clicked.connect(self.export_contacts_file)

        toolbar_card = create_list_page_toolbar(
            "Kisi Rehberi",
            "Karar vericiler ve ilgili kisiler",
            top_actions=[
                add_button,
                quick_action_button,
                self.detail_button,
                self.bulk_count_label,
                self.bulk_button,
                views_button,
                columns_button,
                edit_button,
                delete_button,
                import_button,
                export_button,
            ],
            search_widget=self.search_input,
        )

        self.table = QTableWidget()
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemDoubleClicked.connect(self.edit_selected_contact)
        configure_table(self.table)
        self.table.itemSelectionChanged.connect(self._update_selection_state)
        self.preferences = ListPagePreferences(
            "contacts",
            self.table,
            filter_widgets={"search": self.search_input},
            default_visible_columns=list(range(len(self.headers))),
            reset_callback=self.refresh_table,
        )
        self.preferences.attach_button(columns_button)
        self.preferences.attach_view_button(views_button)

        table_card = create_list_table_card(self.table)

        root_layout.addWidget(toolbar_card)
        root_layout.addWidget(table_card, 1)

        self.preferences.restore()
        self.refresh_table()

    def refresh_table(self) -> None:
        self.contacts = list_contacts(self.search_input.text().strip())
        self.table.setRowCount(len(self.contacts))

        if not self.contacts:
            set_table_empty_state(
                self.table,
                "Arama veya filtre sonucunda gösterilecek kişi bulunamadı.",
                action_label="Yeni Kişi",
                action_handler=self.add_contact,
            )
            self.preferences.finalize_table_state()
            self._update_selection_state()
            return

        for row, contact in enumerate(self.contacts):
            values = [
                contact.name,
                contact.company.name if contact.company else "-",
                contact.title,
                contact.email,
                contact.phone,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value or "-")
                alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                item.setTextAlignment(alignment)
                if column == 0:
                    set_row_identifier(item, contact.id)
                self.table.setItem(row, column, item)

        self.table.resizeColumnsToContents()
        self.preferences.finalize_table_state()
        self._update_selection_state()

    def add_contact(self) -> None:
        dialog = ContactFormDialog(parent=self)
        if dialog.exec():
            create_contact(dialog.get_data())
            self.refresh_table()
            self._notify("Kisi kaydi olusturuldu.")

    def export_contacts_file(self) -> None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Kisileri Disa Aktar",
            get_default_export_path("kisiler.csv"),
            "CSV Dosyalari (*.csv);;Excel Dosyalari (*.xlsx)",
        )
        if not file_path:
            return

        rows = [
            [
                contact.name,
                contact.company.name if contact.company else "",
                contact.title,
                contact.email,
                contact.phone,
            ]
            for contact in self.contacts
        ]
        export_rows(file_path, self.export_headers, rows)
        self._notify("Kisi listesi disa aktarildi.")

    def import_contacts_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Kisileri Ice Aktar",
            get_default_import_dir(),
            "Desteklenen Dosyalar (*.csv *.xlsx)",
        )
        if not file_path:
            return

        summary = import_contacts(file_path)
        self.refresh_table()
        self._show_import_summary("Kisi Ice Aktar", summary.added, summary.updated, summary.skipped, summary.errors)

    def edit_selected_contact(self, _item: QTableWidgetItem | None = None) -> None:
        contact = self._get_selected_contact()
        if not contact:
            self._notify("Lutfen bir kisi secin.", error=True)
            return

        fresh_contact = get_contact(contact.id)
        if not fresh_contact:
            self._notify("Kisi kaydi bulunamadi.", error=True)
            return

        dialog = ContactFormDialog(contact=fresh_contact, parent=self)
        if dialog.exec():
            update_contact(fresh_contact.id, dialog.get_data())
            self.refresh_table()
            self._notify("Kisi kaydi guncellendi.")

    def open_contact_detail(self) -> None:
        contact = self._get_selected_contact()
        if not contact:
            self._notify("Lutfen bir kisi secin.", error=True)
            return

        fresh_contact = get_contact(contact.id)
        if not fresh_contact:
            self._notify("Kisi kaydi bulunamadi.", error=True)
            return

        dialog = ContactDetailDialog(fresh_contact, parent=self)
        dialog.exec()
        self.refresh_table()

    def delete_selected_contact(self) -> None:
        contact = self._get_selected_contact()
        if not contact:
            self._notify("Lutfen bir kisi secin.", error=True)
            return

        answer = QMessageBox.question(
            self,
            "Kisi Sil",
            f"{contact.name} kaydini silmek istiyor musunuz?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            delete_contact(contact.id)
            self.refresh_table()
            self._notify("Kisi kaydi silindi.")

    def _get_selected_contact(self) -> Contact | None:
        selected_ids = get_selected_row_identifiers(self.table)
        if len(selected_ids) != 1:
            return None
        contact_id = selected_ids[0]
        if contact_id is None:
            return None
        return next((contact for contact in self.contacts if contact.id == contact_id), None)

    def _get_selected_contacts(self) -> list[Contact]:
        selected_ids = get_selected_row_identifiers(self.table)
        if not selected_ids:
            return []
        selected_map = {contact.id: contact for contact in self.contacts}
        return [selected_map[contact_id] for contact_id in selected_ids if contact_id in selected_map]

    def _update_selection_state(self) -> None:
        selected_count = len(self._get_selected_contacts())
        self.detail_button.setEnabled(selected_count == 1)
        update_bulk_action_controls(self.bulk_count_label, self.bulk_button, selected_count)

    def bulk_assign_company(self) -> None:
        contacts = self._get_selected_contacts()
        if len(contacts) < 2:
            self._notify("Toplu işlem için en az iki kişi seçin.", error=True)
            return

        companies = list_company_choices()
        if not companies:
            self._notify("Atama için kullanılabilir şirket bulunamadı.", error=True)
            return

        company_labels = [company.name for company in companies]
        selected_label, accepted = QInputDialog.getItem(
            self,
            "Toplu Şirket Ata",
            "Şirket seçin:",
            company_labels,
            0,
            False,
        )
        if not accepted or not selected_label:
            return

        target_company = next((company for company in companies if company.name == selected_label), None)
        if not target_company:
            return

        if not confirm_bulk_action(self, "Toplu Şirket Ata", len(contacts)):
            return

        success_count = 0
        failures: list[str] = []
        for contact in contacts:
            try:
                custom_values = get_field_values("contact", contact.id)
                update_contact(
                    contact.id,
                    {
                        "company_id": target_company.id,
                        "custom_values": custom_values,
                    },
                )
                success_count += 1
            except Exception as exc:
                failures.append(f"{contact.name}: {exc}")

        self.refresh_table()
        show_bulk_result(self, success_count=success_count, failures=failures)

    def quick_create_action(self) -> None:
        contact = self._get_selected_contact()
        if not contact:
            self._notify("Lutfen once bir kisi secin.", error=True)
            return

        dialog = ActionFormDialog(
            initial_company_id=contact.company_id,
            initial_contact_id=contact.id,
            initial_record_type="Kisi",
            initial_action_type="Arama",
            initial_channel="Telefon",
            initial_next_action="Kisiyle ilk temasi kur",
            parent=self,
        )
        if dialog.exec():
            create_action(dialog.get_data())
            self._notify("Kisi icin hizli aksiyon olusturuldu.")

    def _notify(self, message: str, error: bool = False) -> None:
        box = QMessageBox.warning if error else QMessageBox.information
        box(self, "Bilgi", message)

    def _show_import_summary(
        self,
        title: str,
        added: int,
        updated: int,
        skipped: int,
        errors: list[str],
    ) -> None:
        lines = [
            f"Eklenen: {added}",
            f"Guncellenen: {updated}",
            f"Atlanan: {skipped}",
            f"Hata: {len(errors)}",
        ]
        if errors:
            lines.append("")
            lines.extend(errors[:8])
        QMessageBox.information(self, title, "\n".join(lines))
