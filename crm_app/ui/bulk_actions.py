from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from crm_app.ui.styles import set_button_role, style_dialog_buttons


def create_bulk_action_controls() -> tuple[QLabel, QPushButton]:
    count_label = QLabel("Seçili Kayıt Sayısı: 0")
    count_label.setObjectName("SummaryLabel")
    count_label.hide()

    button = QPushButton("Toplu İşlemler")
    set_button_role(button, "ghost")
    button.hide()
    return count_label, button


def update_bulk_action_controls(count_label: QLabel, button: QPushButton, count: int) -> None:
    is_visible = count >= 2
    count_label.setVisible(is_visible)
    button.setVisible(is_visible)
    if is_visible:
        count_label.setText(f"Seçili Kayıt Sayısı: {count}")


def confirm_bulk_action(parent: QWidget, action_label: str, count: int) -> bool:
    answer = QMessageBox.question(
        parent,
        "Toplu İşlem Onayı",
        f"{count} kayıt için '{action_label}' işlemi uygulansın mı?",
    )
    return answer == QMessageBox.StandardButton.Yes


def show_bulk_result(
    parent: QWidget,
    *,
    success_count: int,
    skipped_count: int = 0,
    failures: list[str] | None = None,
) -> None:
    failures = failures or []
    lines = [f"{success_count} kayıt güncellendi."]
    if skipped_count:
        lines.append(f"{skipped_count} kayıt atlandı.")
    if failures:
        lines.append("")
        lines.append("Hatalar:")
        lines.extend(failures[:8])
    QMessageBox.information(parent, "Toplu İşlemler", "\n".join(lines))


class BulkDateDialog(QDialog):
    def __init__(self, title: str, label_text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        form = QFormLayout()
        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate.currentDate())
        form.addRow(label_text, self.date_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        style_dialog_buttons(buttons)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addLayout(form)
        layout.addWidget(buttons)

    def get_value(self) -> date:
        return self.date_input.date().toPython()
