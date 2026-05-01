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

from crm_app.services.auth_service import change_password
from crm_app.ui.styles import apply_shadow, style_dialog_buttons


class ChangePasswordDialog(QDialog):
    def __init__(self, *, user_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._user_id = user_id
        self.setWindowTitle("Şifre Değiştir")
        self.setMinimumSize(560, 380)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header_card = QFrame()
        header_card.setObjectName("DialogCard")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(18, 18, 18, 18)
        header_layout.setSpacing(6)
        apply_shadow(header_card, blur=14, y_offset=2, alpha=10)

        title = QLabel("Şifre Değiştirme Zorunlu")
        title.setObjectName("DialogTitle")
        subtitle = QLabel("Devam etmek için şifrenizi değiştirin. Yeni şifre en az 8 karakter olmalıdır.")
        subtitle.setObjectName("DialogSubtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)

        form_card = QFrame()
        form_card.setObjectName("DialogCard")
        form_layout = QVBoxLayout(form_card)
        form_layout.setContentsMargins(18, 18, 18, 18)
        form_layout.setSpacing(10)

        self.old_password_input = QLineEdit()
        self.old_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password_input = QLineEdit()
        self.new_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password_repeat_input = QLineEdit()
        self.new_password_repeat_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password_repeat_input.returnPressed.connect(self._attempt_change)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)
        form.addRow("Eski Şifre", self.old_password_input)
        form.addRow("Yeni Şifre", self.new_password_input)
        form.addRow("Yeni Şifre (Tekrar)", self.new_password_repeat_input)
        form_layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save_button:
            save_button.setText("Kaydet")
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_button:
            cancel_button.setText("İptal")
        buttons.accepted.connect(self._attempt_change)
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

        self.old_password_input.setFocus()

    def _attempt_change(self) -> None:
        old_password = self.old_password_input.text()
        new_password = self.new_password_input.text()
        new_password_repeat = self.new_password_repeat_input.text()

        if new_password != new_password_repeat:
            QMessageBox.warning(self, "Hata", "Yeni şifreler eşleşmiyor.")
            self.new_password_repeat_input.selectAll()
            self.new_password_repeat_input.setFocus()
            return

        try:
            change_password(
                user_id=self._user_id,
                old_password=old_password,
                new_password=new_password,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Hata", str(exc))
            self.old_password_input.selectAll()
            self.old_password_input.setFocus()
            return

        QMessageBox.information(self, "Başarılı", "Şifreniz güncellendi.")
        self.accept()

