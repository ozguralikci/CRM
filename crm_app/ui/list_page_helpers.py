from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crm_app.ui.styles import create_content_card, create_toolbar_frame, set_button_role, wrap_center_message


def create_list_page_toolbar(
    title: str,
    subtitle: str,
    *,
    top_actions: list[QWidget] | None = None,
    search_widget: QWidget | None = None,
    filter_widgets: list[QWidget] | None = None,
) -> QFrame:
    card = create_toolbar_frame()
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(10)

    title_block = QVBoxLayout()
    title_block.setSpacing(0)
    section_title = QLabel(title)
    section_title.setObjectName("SectionTitle")
    section_subtitle = QLabel(subtitle)
    section_subtitle.setObjectName("SectionSubtitle")
    section_subtitle.setWordWrap(True)
    title_block.addWidget(section_title)
    title_block.addWidget(section_subtitle)

    top_row = QHBoxLayout()
    top_row.setSpacing(8)
    top_row.addLayout(title_block)
    top_row.addStretch()
    for widget in top_actions or []:
        top_row.addWidget(widget)
    layout.addLayout(top_row)

    if search_widget or filter_widgets:
        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)
        if search_widget:
            controls_row.addWidget(search_widget, 1)
        for widget in filter_widgets or []:
            controls_row.addWidget(widget)
        controls_row.addStretch()
        layout.addLayout(controls_row)

    return card


def create_list_table_card(table: QWidget) -> QFrame:
    card = create_content_card()
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.addWidget(table)
    return card


def set_table_empty_state(
    table: QTableWidget,
    message: str,
    *,
    action_label: str | None = None,
    action_handler: object | None = None,
) -> None:
    table.clearSpans()
    table.clearContents()
    table.setRowCount(1)
    column_count = max(table.columnCount(), 1)
    title = "Henüz kayıt yok" if action_label else "Sonuç bulunamadı"
    empty_card = wrap_center_message(title, message)
    empty_card.setContentsMargins(0, 0, 0, 0)

    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(10)
    layout.addWidget(empty_card, 0, Qt.AlignmentFlag.AlignCenter)

    if action_label and callable(action_handler):
        action_button = QPushButton(action_label)
        set_button_role(action_button, "secondary")
        action_button.setMinimumWidth(136)
        action_button.clicked.connect(action_handler)
        layout.addWidget(action_button, 0, Qt.AlignmentFlag.AlignCenter)

    layout.addStretch(1)
    placeholder_item = QTableWidgetItem("")
    placeholder_item.setFlags(Qt.ItemFlag.NoItemFlags)
    table.setItem(0, 0, placeholder_item)
    table.setSpan(0, 0, 1, column_count)
    table.setCellWidget(0, 0, container)
    table.resizeColumnsToContents()
