from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from crm_app.ui.styles import create_content_card, create_toolbar_frame


class SurfacePanel(QFrame):
    def __init__(
        self,
        title: str,
        subtitle: str = "",
        *,
        surface: str = "content",
        accent: str | None = None,
        trailing_widgets: list[QWidget] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        trailing_widgets = trailing_widgets or []
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        if accent is not None or surface == "dashboard":
            accent = accent or "default"
            self.setObjectName("DashboardPanel")
            self.setProperty("accent", accent)

            layout = QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)

            accent_line = QFrame()
            accent_line.setObjectName("PanelAccentLine")
            accent_line.setProperty("tone", accent if accent != "default" else "base")

            header_container = QWidget()
            header_layout = QHBoxLayout(header_container)
            header_layout.setContentsMargins(16, 12, 16, 10)
            header_layout.setSpacing(8)

            title_block = self._build_title_block(title, subtitle)
            header_layout.addLayout(title_block, 1)
            for widget in trailing_widgets:
                header_layout.addWidget(widget)

            self.body_layout = QVBoxLayout()
            self.body_layout.setContentsMargins(14, 0, 14, 12)
            self.body_layout.setSpacing(8)

            layout.addWidget(accent_line)
            layout.addWidget(header_container)
            layout.addLayout(self.body_layout)
            return

        template = create_toolbar_frame() if surface == "toolbar" else create_content_card()
        self.setObjectName(template.objectName())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)
        header_row.addLayout(self._build_title_block(title, subtitle), 1)
        for widget in trailing_widgets:
            header_row.addWidget(widget)

        self.body_layout = QVBoxLayout()
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(8)

        layout.addLayout(header_row)
        layout.addLayout(self.body_layout)

    def _build_title_block(self, title: str, subtitle: str) -> QVBoxLayout:
        title_block = QVBoxLayout()
        title_block.setSpacing(2 if subtitle else 0)

        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle" if self.objectName() != "DashboardPanel" else "PanelTitle")
        title_block.addWidget(title_label)

        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName(
                "SectionSubtitle" if self.objectName() != "DashboardPanel" else "PanelSubtitle"
            )
            subtitle_label.setWordWrap(True)
            title_block.addWidget(subtitle_label)
        return title_block


def create_compact_stat_card(
    title: str,
    value: str = "-",
    *,
    surface: str = "content",
    value_object_name: str = "SummaryValue",
) -> tuple[QFrame, QLabel]:
    card = create_toolbar_frame() if surface == "toolbar" else create_content_card()
    card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(12, 11, 12, 11)
    layout.setSpacing(3)

    title_label = QLabel(title)
    title_label.setObjectName("SummaryLabel")
    value_label = QLabel(value)
    value_label.setObjectName(value_object_name)

    layout.addWidget(title_label)
    layout.addWidget(value_label)
    return card, value_label
