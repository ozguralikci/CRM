from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from crm_app.services.auth_service import authenticate
from crm_app.ui.styles import apply_shadow, style_dialog_buttons


class LoginDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Giriş")
        self.setMinimumSize(520, 320)
        self.authenticated_username: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header_card = QFrame()
        header_card.setObjectName("DialogCard")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(6)
        apply_shadow(header_card, blur=14, y_offset=2, alpha=10)

        title = QLabel("CRM Girişi")
        title.setObjectName("DialogTitle")
        subtitle = QLabel("Devam etmek için kullanıcı bilgilerinizi girin.")
        subtitle.setObjectName("DialogSubtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        form_card = QFrame()
        form_card.setObjectName("DialogCard")
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(18, 18, 18, 18)
        form_layout.setSpacing(10)

        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self._attempt_login)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)
        form.addRow("Kullanıcı Adı", self.username_input)
        form.addRow("Şifre", self.password_input)
        form_layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button:
            ok_button.setText("Giriş")
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_button:
            cancel_button.setText("İptal")
        buttons.accepted.connect(self._attempt_login)
        buttons.rejected.connect(self.reject)
        style_dialog_buttons(buttons)

        footer_card = QFrame()
        footer_card.setObjectName("DialogCard")
        footer_layout = QVBoxLayout(footer_card)
        footer_layout.setContentsMargins(18, 12, 18, 12)
        footer_layout.addWidget(buttons)
        footer_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout.addWidget(header_card)
        layout.addWidget(form_card, 1)
        layout.addWidget(footer_card)

        self.username_input.setFocus()

    def _attempt_login(self) -> None:
        username = self.username_input.text().strip()
        password = self.password_input.text()
        user = authenticate(username, password)
        if not user:
            QMessageBox.warning(self, "Giriş Başarısız", "Kullanıcı adı veya şifre hatalı.")
            self.password_input.selectAll()
            self.password_input.setFocus()
            return
        self.authenticated_username = user.username
        self.accept()

