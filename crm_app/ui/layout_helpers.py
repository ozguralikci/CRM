from __future__ import annotations

from dataclasses import dataclass
import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QScrollArea, QSizePolicy, QVBoxLayout, QWidget


def create_scroll_area(
    *,
    max_content_width: int | None = None,
    spacing: int = 12,
) -> tuple[QScrollArea, QWidget, QVBoxLayout]:
    scroll_area = QScrollArea()
    scroll_area.setWidgetResizable(True)
    scroll_area.setFrameShape(QFrame.Shape.NoFrame)
    scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    viewport = QWidget()
    viewport_layout = QHBoxLayout(viewport)
    viewport_layout.setContentsMargins(0, 0, 0, 0)
    viewport_layout.setSpacing(0)

    content = QWidget()
    content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    if max_content_width is not None:
        content.setMaximumWidth(max_content_width)
        viewport_layout.addStretch(1)
        viewport_layout.addWidget(content, 1)
        viewport_layout.addStretch(1)
    else:
        viewport_layout.addWidget(content)

    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(0, 0, 0, 0)
    content_layout.setSpacing(spacing)

    scroll_area.setWidget(viewport)
    return scroll_area, content, content_layout


class ResponsiveGridSection(QWidget):
    def __init__(
        self,
        *,
        min_column_width: int = 320,
        max_columns: int | None = None,
        horizontal_spacing: int = 12,
        vertical_spacing: int = 12,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.min_column_width = max(1, min_column_width)
        self.max_columns = max_columns
        self._items: list[ResponsiveGridItem] = []
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(0, 0, 0, 0)
        self._grid.setHorizontalSpacing(horizontal_spacing)
        self._grid.setVerticalSpacing(vertical_spacing)

    def add_responsive_widget(
        self,
        widget: QWidget,
        *,
        role: str = "compact",
        preferred_span: int | None = None,
        min_width: int | None = None,
    ) -> None:
        self._items.append(
            ResponsiveGridItem(
                widget=widget,
                role=role,
                preferred_span=preferred_span,
                min_width=min_width,
            )
        )
        self._relayout()

    def set_items(self, items: list["ResponsiveGridItem"]) -> None:
        self._items = list(items)
        self._relayout()

    def set_widgets(self, widgets: list[QWidget]) -> None:
        self.set_items([ResponsiveGridItem(widget=widget) for widget in widgets])

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._relayout()

    def _clear_grid(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(self)

    def _calculate_column_count(self) -> int:
        item_count = len(self._items)
        if item_count <= 1:
            return item_count

        available_width = max(self.width(), self.sizeHint().width(), self.min_column_width)
        estimated_columns = max(1, available_width // self.min_column_width)
        if self.max_columns is not None:
            estimated_columns = min(estimated_columns, self.max_columns)
        return min(item_count, estimated_columns)

    def _role_min_width(self, item: "ResponsiveGridItem") -> int:
        if item.min_width is not None:
            return item.min_width
        defaults = {
            "anchor": 520,
            "compact": 180,
            "medium": 260,
            "support": 280,
            "text": 420,
            "table": 460,
            "full": 620,
        }
        return defaults.get(item.role, self.min_column_width)

    def _span_for(self, item: "ResponsiveGridItem", column_count: int, unit_width: float) -> int:
        if column_count <= 1:
            return 1
        if item.preferred_span is not None:
            base_span = max(1, min(item.preferred_span, column_count))
        elif item.role == "full":
            base_span = column_count
        elif item.role == "anchor":
            base_span = min(column_count, 2 if column_count >= 3 else column_count)
        elif item.role == "support":
            base_span = 1
        elif item.role == "table":
            base_span = min(column_count, 2 if column_count <= 3 else 3)
        elif item.role == "text":
            base_span = min(column_count, 2 if column_count <= 3 else 3)
        elif item.role == "medium":
            base_span = min(column_count, 2 if column_count >= 4 else 1)
        else:
            base_span = 1

        required_span = max(1, math.ceil(self._role_min_width(item) / max(unit_width, 1)))
        return min(column_count, max(base_span, required_span))

    def _relayout(self) -> None:
        if not self._items:
            return

        column_count = self._calculate_column_count()
        self._clear_grid()
        spacing = self._grid.horizontalSpacing()
        available_width = max(self.width(), self.sizeHint().width(), self.min_column_width)
        usable_width = max(available_width - (spacing * max(column_count - 1, 0)), self.min_column_width)
        unit_width = usable_width / max(column_count, 1)
        row = 0
        column = 0
        for item in self._items:
            span = self._span_for(item, column_count, unit_width)
            if column + span > column_count:
                row += 1
                column = 0
            self._grid.addWidget(item.widget, row, column, 1, span)
            column += span
            if column >= column_count:
                row += 1
                column = 0
        for column in range(column_count):
            self._grid.setColumnStretch(column, 1)


@dataclass(slots=True)
class ResponsiveGridItem:
    widget: QWidget
    role: str = "compact"
    preferred_span: int | None = None
    min_width: int | None = None
