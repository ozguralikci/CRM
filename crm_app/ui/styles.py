from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialogButtonBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)


def apply_shadow(widget: QWidget, blur: int = 18, y_offset: int = 3, alpha: int = 14) -> None:
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, y_offset)
    shadow.setColor(QColor(15, 23, 42, alpha))
    widget.setGraphicsEffect(shadow)


def set_button_role(button: QPushButton, role: str) -> None:
    button.setProperty("variant", role)
    button.setMinimumHeight(34)
    button.style().unpolish(button)
    button.style().polish(button)


def style_dialog_buttons(button_box: QDialogButtonBox) -> None:
    save_button = button_box.button(QDialogButtonBox.StandardButton.Save)
    cancel_button = button_box.button(QDialogButtonBox.StandardButton.Cancel)

    if save_button:
        save_button.setText("Kaydet")
        set_button_role(save_button, "primary")

    if cancel_button:
        cancel_button.setText("Iptal")
        set_button_role(cancel_button, "secondary")


def configure_table(table: QTableWidget) -> None:
    table.setObjectName("AppTable")
    table.setAlternatingRowColors(False)
    table.setShowGrid(False)
    table.setWordWrap(False)
    table.setCornerButtonEnabled(False)
    table.setSortingEnabled(False)
    table.setStyleSheet("")
    table.setMouseTracking(True)
    table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.verticalHeader().setDefaultSectionSize(34)


def create_page_header(title: str, subtitle: str) -> QFrame:
    frame = QFrame()
    frame.setObjectName("PageHeaderCard")

    layout = QVBoxLayout(frame)
    layout.setContentsMargins(2, 0, 2, 8)
    layout.setSpacing(1)

    eyebrow = QLabel("CRM")
    eyebrow.setObjectName("PageEyebrow")

    title_label = QLabel(title)
    title_label.setObjectName("PageTitle")

    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("PageSubtitle")
    subtitle_label.setWordWrap(True)

    layout.addWidget(eyebrow)
    layout.addWidget(title_label)
    layout.addWidget(subtitle_label)
    return frame


def create_toolbar_frame() -> QFrame:
    frame = QFrame()
    frame.setObjectName("ToolbarCard")
    return frame


def create_content_card() -> QFrame:
    frame = QFrame()
    frame.setObjectName("ContentCard")
    return frame


def wrap_center_message(title: str, description: str) -> QFrame:
    frame = QFrame()
    frame.setObjectName("EmptyStateCard")
    frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    layout = QVBoxLayout(frame)
    layout.setContentsMargins(30, 24, 30, 22)
    layout.setSpacing(8)

    title_label = QLabel(title)
    title_label.setObjectName("EmptyStateTitle")
    title_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)

    description_label = QLabel(description)
    description_label.setObjectName("EmptyStateDescription")
    description_label.setWordWrap(True)
    description_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)

    layout.addWidget(title_label)
    layout.addWidget(description_label)
    return frame


def build_stylesheet() -> str:
    return """
    * {
        font-family: "Segoe UI Variable Text", "Segoe UI";
        color: #162033;
        font-size: 13px;
    }
    QMainWindow, QWidget {
        background: #f6f8fb;
    }
    #MainShell {
        background: #f6f8fb;
    }
    #SidebarPanel {
        background: transparent;
    }
    #BrandCard {
        background: transparent;
        border: none;
        border-bottom: 1px solid #e4eaf2;
    }
    #BrandTitle {
        color: #0f172a;
        font-size: 19px;
        font-weight: 700;
    }
    #BrandSubtitle {
        color: #758398;
        font-size: 11px;
    }
    #BrandMark {
        background: #1d4ed8;
        border-radius: 5px;
        min-width: 10px;
        max-width: 10px;
        min-height: 10px;
        max-height: 10px;
    }
    #SidebarMenu {
        background: transparent;
        border: none;
        outline: none;
        padding: 6px 4px;
    }
    #SidebarMenu::item {
        background: transparent;
        border-radius: 10px;
        padding: 10px 12px;
        margin: 2px 0;
        color: #4f5f75;
        font-size: 13px;
        font-weight: 600;
    }
    #SidebarMenu::item:hover {
        background: #eef3f8;
        color: #173b73;
    }
    #SidebarMenu::item:selected {
        background: #e9f0ff;
        color: #1746a2;
        border-left: 2px solid #1d4ed8;
    }
    #PageViewport {
        background: transparent;
    }
    #PageFrame {
        background: transparent;
    }
    #PageHeaderCard {
        background: transparent;
        border: none;
        border-bottom: 1px solid #e7edf4;
        border-radius: 0;
    }
    #ToolbarCard, #ContentCard, #MetricCard, #EmptyStateCard, #DialogCard {
        background: #ffffff;
        border: 1px solid #e6ebf2;
        border-radius: 14px;
    }
    #CompanyOperationsSplitter {
        background: transparent;
    }
    #CompanyOperationsSplitter::handle {
        background: transparent;
        margin: 0 2px;
    }
    #CompanyOperationsSplitter::handle:horizontal {
        min-width: 6px;
    }
    #CompanyOperationsSplitter::handle:horizontal:hover {
        background: #edf2f8;
        border-radius: 3px;
    }
    #CompanyOperationsSplitter::handle:horizontal:pressed {
        background: #e2e9f3;
        border-radius: 3px;
    }
    #DashboardPanel {
        background: #ffffff;
        border: 1px solid #eaf0f6;
        border-radius: 14px;
    }
    #DashboardPanel[accent="alert"] {
        border: 1px solid #f2e2df;
        background: #fffdfd;
    }
    #DashboardPanel[accent="focus"] {
        border: 1px solid #e3ecfb;
        background: #fdfefe;
    }
    #PanelAccentLine {
        min-height: 1px;
        max-height: 1px;
        border-radius: 2px;
        background: #e6edf7;
    }
    #PanelAccentLine[tone="alert"] {
        background: #efc7c2;
    }
    #PanelAccentLine[tone="focus"] {
        background: #9ab9f7;
    }
    #PageEyebrow {
        color: #6e7d91;
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.8px;
    }
    #PageTitle {
        color: #0f172a;
        font-size: 25px;
        font-weight: 700;
    }
    #PageSubtitle {
        color: #748397;
        font-size: 11px;
    }
    #ToolbarCard {
        background: #f9fbfd;
        border: 1px solid #e7edf4;
    }
    #ToolbarCard[header_role="summary"] {
        background: #fbfcfe;
    }
    #ToolbarCard[header_role="decision"] {
        background: #f9fbfd;
    }
    #ContentCard[header_role="actions"] {
        background: #ffffff;
        border: 1px solid #dfe8f7;
    }
    #ContentCard[workspace_role="kpi-strip"] {
        border: 1px solid #e8edf4;
    }
    #ToolbarCard[workspace_role="kpi-block"] {
        background: #fbfcfe;
        border: 1px solid #e7edf4;
        border-radius: 12px;
    }
    #ToolbarCard[workspace_role="quick-actions"] {
        background: #f9fbfd;
        border: 1px solid #e4eaf2;
    }
    #ToolbarCard[workspace_role="focus"] {
        background: #fbfcff;
        border: 1px solid #dfe8f7;
    }
    #ToolbarCard[workspace_role="focus"] #SectionTitle {
        color: #173156;
    }
    #ToolbarCard[workspace_role="focus"] #SectionSubtitle {
        color: #667991;
    }
    #ToolbarCard[workspace_role="quick-actions"] QPushButton {
        min-width: 104px;
    }
    #ToolbarCard[workspace_role="quick-actions"] #SectionSubtitle {
        color: #6f8097;
    }
    #ToolbarCard[workspace_role="operations"],
    #ContentCard[workspace_role="operations"] {
        border: 1px solid #e7edf4;
    }
    #ToolbarCard[workspace_role="kpi-block"] #SectionSubtitle {
        color: #6f8097;
    }
    #ToolbarCard[workspace_role="kpi-block"] #SectionTitle {
        color: #10233a;
    }
    #SectionTitle {
        color: #102036;
        font-size: 14px;
        font-weight: 700;
    }
    #SectionSubtitle {
        color: #728197;
        font-size: 11px;
        font-weight: 500;
    }
    #SummaryLabel {
        color: #6d7e93;
        font-size: 11px;
        font-weight: 600;
    }
    #SummaryValue {
        color: #11243a;
        font-size: 13px;
        font-weight: 600;
        background: transparent;
    }
    #PanelTitle {
        color: #0f1d31;
        font-size: 14px;
        font-weight: 700;
    }
    #PanelSubtitle {
        color: #6f7f95;
        font-size: 11px;
    }
    #PriorityPill {
        background: #fbfcfe;
        color: #6f8097;
        border-radius: 9px;
        border: 1px solid #e5ebf2;
        padding: 4px 8px;
        font-size: 10px;
        font-weight: 700;
    }
    QLineEdit, QComboBox, QSpinBox, QTextEdit, QDateEdit, QTimeEdit {
        background: #ffffff;
        border: 1px solid #d8e0eb;
        border-radius: 10px;
        padding: 0 10px;
        min-height: 34px;
        selection-background-color: #dbeafe;
    }
    QTextEdit {
        padding: 8px 10px;
        min-height: 78px;
    }
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus, QDateEdit:focus, QTimeEdit:focus {
        border: 1px solid #2563eb;
        background: #fcfdff;
    }
    QComboBox::drop-down, QDateEdit::drop-down, QTimeEdit::drop-down {
        border: none;
        width: 24px;
    }
    QPushButton {
        border-radius: 10px;
        padding: 0 14px;
        min-height: 34px;
        font-weight: 600;
    }
    QPushButton[variant="primary"] {
        background: #1d4ed8;
        color: white;
        border: 1px solid #1d4ed8;
    }
    QPushButton[variant="primary"]:hover {
        background: #1e40af;
        border: 1px solid #1e40af;
    }
    QPushButton[variant="primary"]:pressed {
        background: #17368d;
        border: 1px solid #17368d;
    }
    QPushButton[variant="secondary"] {
        background: #ffffff;
        color: #334155;
        border: 1px solid #d8e0eb;
    }
    QPushButton[variant="secondary"]:hover {
        background: #f7f9fc;
    }
    QPushButton[variant="secondary"]:pressed {
        background: #eef2f7;
        border: 1px solid #cfd8e4;
    }
    QPushButton[variant="ghost"] {
        background: #f8fafc;
        color: #4d6078;
        border: 1px solid #e1e8f0;
    }
    QPushButton[variant="ghost"]:hover {
        background: #eef3f8;
    }
    QPushButton[variant="ghost"]:pressed {
        background: #e7edf5;
        border: 1px solid #d7e0eb;
    }
    QPushButton[variant="danger"] {
        background: #fff8f7;
        color: #b14443;
        border: 1px solid #ecd4d1;
    }
    QPushButton[variant="danger"]:hover {
        background: #fff1ef;
    }
    #SummaryValue[context="link-descriptor"] {
        color: #23354a;
        font-size: 12px;
        font-weight: 600;
    }
    #SummaryValue[context="summary-supporting"] {
        color: #28405a;
        font-size: 12px;
        font-weight: 500;
    }
    QWidget[context="link-actions"] {
        background: transparent;
    }
    QPushButton[context="link-action"] {
        min-height: 28px;
        padding: 0 10px;
        border-radius: 8px;
        font-size: 11px;
        font-weight: 600;
    }
    QPushButton[variant="ghost"][context="link-action"] {
        background: #fbfcfe;
        color: #607187;
        border: 1px solid #e6edf4;
    }
    QPushButton[variant="ghost"][context="link-action"]:hover {
        background: #f2f6fa;
        color: #31455d;
        border: 1px solid #d9e3ee;
    }
    QPushButton[variant="ghost"][context="link-action"]:pressed {
        background: #edf2f7;
        color: #27384d;
        border: 1px solid #d2dbe6;
    }
    QMenu {
        background: #ffffff;
        border: 1px solid #e4eaf2;
        border-radius: 12px;
        padding: 8px;
    }
    QMenu::item {
        padding: 8px 12px;
        border-radius: 8px;
        color: #243449;
    }
    QMenu::item:selected {
        background: #eef4ff;
        color: #1d4ed8;
    }
    QMenu::separator {
        height: 1px;
        background: #edf2f7;
        margin: 6px 4px;
    }
    #AppTable {
        background: #ffffff;
        border: 1px solid #f1f4f8;
        border-radius: 10px;
        gridline-color: transparent;
        selection-background-color: #eef4ff;
        selection-color: #0f213b;
        color: #1a2638;
        outline: none;
        font-size: 12px;
    }
    #AppTable::item {
        padding: 6px 10px;
        border-bottom: 1px solid #f5f7fa;
        background: transparent;
        color: #1a2638;
        font-size: 12px;
    }
    #AppTable::item:hover {
        background: #f8fbff;
    }
    #AppTable[interactive="true"]::item:hover {
        background: #f2f7ff;
    }
    QHeaderView::section {
        background: #f9fbfd;
        color: #5d6d83;
        border: none;
        border-bottom: 1px solid #eef2f6;
        padding: 10px 10px;
        font-size: 10px;
        font-weight: 700;
    }
    QScrollBar:vertical {
        background: transparent;
        width: 12px;
        margin: 8px 2px;
    }
    QScrollBar::handle:vertical {
        background: #cfd8e6;
        border-radius: 6px;
        min-height: 30px;
    }
    QScrollBar::handle:vertical:hover {
        background: #b9c6d8;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        background: transparent;
        border: none;
    }
    QScrollBar:horizontal {
        background: transparent;
        height: 12px;
        margin: 2px 8px;
    }
    QScrollBar::handle:horizontal {
        background: #cfd8e6;
        border-radius: 6px;
        min-width: 30px;
    }
    QScrollBar::handle:horizontal:hover {
        background: #b9c6d8;
    }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
        background: transparent;
        border: none;
        width: 0;
    }
    #MetricTitle {
        color: #66768d;
        font-size: 10px;
        font-weight: 700;
    }
    #MetricValue {
        color: #101827;
        font-size: 31px;
        font-weight: 700;
    }
    #MetricHint {
        color: #7e8d9f;
        font-size: 9px;
        font-weight: 400;
    }
    #MetricCard {
        background: #fdfefe;
        border: 1px solid #f1f4f8;
    }
    #MetricCard[tone="blue"] {
        border-top: 1px solid #8bb0f5;
    }
    #MetricCard[tone="slate"] {
        border-top: 1px solid #c0cbda;
    }
    #MetricCard[tone="indigo"] {
        border-top: 1px solid #a9b8f5;
    }
    #MetricCard[tone="rose"] {
        border-top: 1px solid #e8c4bf;
    }
    #MetricCard[tone="amber"] {
        border-top: 1px solid #e4d3aa;
    }
    #WorkspaceTabs::pane {
        border: 1px solid #e6ebf2;
        background: #ffffff;
        border-radius: 14px;
        top: -1px;
    }
    #WorkspaceTabs QTabBar {
        background: transparent;
    }
    #WorkspaceTabs QTabBar::tab {
        background: transparent;
        color: #607188;
        border: none;
        padding: 10px 14px;
        margin-right: 4px;
        border-top-left-radius: 10px;
        border-top-right-radius: 10px;
        font-size: 12px;
        font-weight: 600;
    }
    #WorkspaceTabs QTabBar::tab:hover {
        background: #f3f7fc;
        color: #23406f;
    }
    #WorkspaceTabs QTabBar::tab:selected {
        background: #ffffff;
        color: #1d4ed8;
        border-bottom: 2px solid #1d4ed8;
    }
    QDialog {
        background: #f6f8fb;
    }
    QLabel[role="form-label"] {
        color: #50627b;
        font-weight: 600;
    }
    #DialogTitle {
        color: #0f172a;
        font-size: 21px;
        font-weight: 700;
    }
    #DialogSubtitle {
        color: #718198;
        font-size: 12px;
    }
    QMessageBox {
        background: #f6f8fb;
    }
    #EmptyStateTitle {
        color: #13213a;
        font-size: 18px;
        font-weight: 700;
        background: transparent;
    }
    #EmptyStateDescription {
        color: #74859a;
        font-size: 12px;
        background: transparent;
    }
    """
