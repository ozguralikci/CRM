from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
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

from crm_app.services.user_service import create_user, list_users
from crm_app.ui.styles import apply_shadow, create_content_card


class UsersPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        header = QFrame()
        header.setObjectName("ToolbarCard")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 16, 18, 16)
        header_layout.setSpacing(6)
        apply_shadow(header, blur=14, y_offset=2, alpha=10)

        title = QLabel("Kullanıcılar")
        title.setObjectName("SectionTitle")
        subtitle = QLabel("Yeni kullanıcı ekleyin ve mevcut kullanıcıları listeleyin.")
        subtitle.setObjectName("SectionSubtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        form_card = create_content_card()
        form_layout = QHBoxLayout(form_card)
        form_layout.setContentsMargins(16, 16, 16, 16)
        form_layout.setSpacing(10)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Kullanıcı adı")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Şifre (en az 8 karakter)")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        add_button = QPushButton("Ekle")
        add_button.clicked.connect(self._on_add_user)

        form_layout.addWidget(self.username_input, 2)
        form_layout.addWidget(self.password_input, 2)
        form_layout.addWidget(add_button, 0)

        table_card = create_content_card()
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(12, 12, 12, 12)
        table_layout.setSpacing(8)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["ID", "Kullanıcı Adı", "Şifre Değiştirme"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        table_layout.addWidget(self.table)

        layout.addWidget(header)
        layout.addWidget(form_card)
        layout.addWidget(table_card, 1)

        self.refresh_table()

    def refresh_table(self) -> None:
        users = list_users()
        self.table.setRowCount(len(users))
        for row, user in enumerate(users):
            self.table.setItem(row, 0, QTableWidgetItem(str(user.id)))
            self.table.setItem(row, 1, QTableWidgetItem(user.username))
            flag = "Evet" if getattr(user, "must_change_password", False) else "Hayır"
            self.table.setItem(row, 2, QTableWidgetItem(flag))

        self.table.resizeColumnsToContents()

    def _on_add_user(self) -> None:
        username = self.username_input.text().strip()
        password = self.password_input.text()
        try:
            create_user(username=username, password=password)
        except Exception as exc:
            QMessageBox.warning(self, "Hata", str(exc))
            return

        QMessageBox.information(self, "Başarılı", "Kullanıcı oluşturuldu.")
        self.password_input.clear()
        self.refresh_table()

