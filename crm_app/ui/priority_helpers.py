from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QTableWidget, QTableWidgetItem, QWidget

FILLED_STAR = "★"
EMPTY_STAR = "☆"
FILLED_COLOR = "#F4B400"
EMPTY_COLOR = "#cfd7e3"


def _priority_level_text(priority: int) -> str:
    if priority <= 2:
        return "Düşük"
    if priority == 3:
        return "Orta"
    return "Yüksek"


def build_priority_html(priority: int, *, font_size: int = 12) -> str:
    safe_priority = max(1, min(5, int(priority)))
    filled = "".join(
        f"<span style='color:{FILLED_COLOR};'>{FILLED_STAR}</span>" for _ in range(safe_priority)
    )
    empty = "".join(
        f"<span style='color:{EMPTY_COLOR};'>{EMPTY_STAR}</span>" for _ in range(5 - safe_priority)
    )
    return (
        f"<span style='font-size:{font_size}px; letter-spacing:0.5px;'>"
        f"{filled}{empty}"
        "</span>"
    )


def build_priority_tooltip(priority: int) -> str:
    safe_priority = max(1, min(5, int(priority)))
    return f"Öncelik: {safe_priority} ({_priority_level_text(safe_priority)})"


def create_priority_label(priority: int, *, font_size: int = 12, centered: bool = True) -> QLabel:
    label = QLabel()
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setText(build_priority_html(priority, font_size=font_size))
    label.setToolTip(build_priority_tooltip(priority))
    label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
    if centered:
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    return label


class PriorityTableItem(QTableWidgetItem):
    def __init__(self, priority: int) -> None:
        super().__init__("")
        self.priority = max(1, min(5, int(priority)))
        self.setToolTip(build_priority_tooltip(self.priority))
        self.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

    def __lt__(self, other: QTableWidgetItem) -> bool:
        if isinstance(other, PriorityTableItem):
            return self.priority < other.priority
        return super().__lt__(other)


def set_priority_table_cell(table: QTableWidget, row: int, column: int, priority: int) -> None:
    item = PriorityTableItem(priority)
    table.setItem(row, column, item)

    container = QWidget()
    container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
    container.setToolTip(build_priority_tooltip(priority))
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addStretch(1)
    layout.addWidget(create_priority_label(priority, centered=True))
    layout.addStretch(1)
    table.setCellWidget(row, column, container)
