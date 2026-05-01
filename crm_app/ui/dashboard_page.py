from __future__ import annotations

from textwrap import shorten

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crm_app.models import Action, Company
from crm_app.services.action_service import create_action
from crm_app.services.company_service import get_company, get_company_pipeline_counts
from crm_app.services.contact_service import create_contact
from crm_app.services.dashboard_service import (
    get_commercial_metrics,
    get_dashboard_metrics,
    get_pipeline_summary,
    get_sample_status_summary,
    list_hot_companies,
    list_overdue_actions,
    list_recent_actions,
    list_todays_followups,
)
from crm_app.services.followup_service import FollowUpAlert, list_smart_followup_alerts
from crm_app.services.opportunity_service import create_opportunity
from crm_app.ui.layout_helpers import ResponsiveGridItem, ResponsiveGridSection, create_scroll_area
from crm_app.ui.action_form import ActionFormDialog
from crm_app.ui.companies_page import CompanyDetailDialog
from crm_app.ui.contact_form import ContactFormDialog
from crm_app.ui.opportunity_form import OpportunityFormDialog
from crm_app.ui.priority_helpers import set_priority_table_cell
from crm_app.ui.styles import (
    apply_shadow,
    configure_table,
    create_page_header,
    create_toolbar_frame,
    set_button_role,
)
from crm_app.ui.surface_helpers import SurfacePanel


class MetricCard(QFrame):
    def __init__(
        self,
        title: str,
        value: int | float | str,
        hint: str,
        tone: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self.setProperty("tone", tone)
        self.setMinimumHeight(98)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setObjectName("MetricTitle")

        value_label = QLabel(str(value))
        value_label.setObjectName("MetricValue")
        value_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        hint_label = QLabel(hint)
        hint_label.setObjectName("MetricHint")
        hint_label.setWordWrap(True)

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(hint_label)
        apply_shadow(self, blur=10, y_offset=1, alpha=6)


class DashboardPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        shell_layout = QVBoxLayout(self)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        scroll_area, _scroll_content, root_layout = create_scroll_area(spacing=12)
        root_layout.setContentsMargins(8, 8, 8, 8)

        root_layout.addWidget(
            create_page_header(
                "Dashboard",
                "Satis operasyonlarinizin genel durumunu tek bakista izleyin.",
            )
        )

        self.pipeline_counts_frame = create_toolbar_frame()
        self.pipeline_counts_frame.setProperty("header_role", "summary")
        apply_shadow(self.pipeline_counts_frame, blur=12, y_offset=2, alpha=8)
        pipeline_layout = QHBoxLayout(self.pipeline_counts_frame)
        pipeline_layout.setContentsMargins(12, 10, 12, 10)
        pipeline_layout.setSpacing(10)

        self.pipeline_count_labels: dict[str, QLabel] = {}
        for key, label in [
            ("total", "Toplam Şirket"),
            ("lead", "Lead"),
            ("contacted", "Contacted"),
            ("meeting", "Meeting"),
            ("offer", "Offer"),
            ("won", "Won"),
            ("lost", "Lost"),
        ]:
            chip = QLabel(f"{label}: -")
            chip.setObjectName("SummaryValue")
            chip.setProperty("context", "summary-supporting")
            chip.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.pipeline_count_labels[key] = chip
            pipeline_layout.addWidget(chip)
        pipeline_layout.addStretch(1)
        root_layout.addWidget(self.pipeline_counts_frame)

        self.cards_section = ResponsiveGridSection(
            min_column_width=260,
            max_columns=3,
            horizontal_spacing=12,
            vertical_spacing=10,
        )
        root_layout.addWidget(self.cards_section)

        support_layout = QGridLayout()
        support_layout.setHorizontalSpacing(14)
        support_layout.setVerticalSpacing(14)

        self.alerts_panel = SurfacePanel(
            "Akıllı Takip Uyarıları",
            "Operasyonel dikkat gerektiren kayıtları görün ve güvenli sonraki adımı başlatın.",
            surface="dashboard",
            accent="focus",
        )
        self.alerts_container = QWidget()
        self.alerts_layout = QVBoxLayout(self.alerts_container)
        self.alerts_layout.setContentsMargins(0, 0, 0, 0)
        self.alerts_layout.setSpacing(8)
        self.alerts_panel.body_layout.addWidget(self.alerts_container)
        self.alerts_panel.setMinimumHeight(216)

        self.today_panel = SurfacePanel(
            "Bugun Yapilacaklar",
            "Bugun takip edilmesi gereken planli aksiyonlar.",
            surface="dashboard",
            accent="focus",
        )
        self.today_table = self._create_action_table(
            ["Sirket", "Kisi", "Aksiyon", "Not"],
            clickable=False,
        )
        self.today_panel.body_layout.addWidget(self.today_table)
        self.today_panel.setMinimumHeight(316)

        self.overdue_panel = SurfacePanel(
            "Geciken Aksiyonlar",
            "Takvimde gecikmis ve oncelik verilmesi gereken kayitlar.",
            surface="dashboard",
            accent="alert",
        )
        self.overdue_table = self._create_action_table(
            ["Tarih", "Sirket", "Kisi", "Sonraki Aksiyon"],
            clickable=False,
        )
        self.overdue_panel.body_layout.addWidget(self.overdue_table)
        self.overdue_panel.setMinimumHeight(316)

        self.hot_companies_panel = SurfacePanel(
            "Sicak Firmalar",
            "Yuksek oncelikli ve yakin takip gerektiren firmalar.",
            surface="dashboard",
        )
        self.hot_companies_table = self._create_company_table()
        self.hot_companies_panel.body_layout.addWidget(self.hot_companies_table)
        self.hot_companies_panel.setMinimumHeight(316)

        self.recent_actions_panel = SurfacePanel(
            "Son Aksiyonlar",
            "Sistemde son kaydedilen temaslar.",
            surface="dashboard",
        )
        self.recent_actions_table = self._create_action_table(
            ["Tarih", "Sirket", "Aksiyon"],
            clickable=False,
        )
        self.recent_actions_panel.body_layout.addWidget(self.recent_actions_table)
        self.recent_actions_panel.setMinimumHeight(316)

        support_layout.addWidget(self.alerts_panel, 0, 0, 1, 2)
        support_layout.addWidget(self.today_panel, 1, 0)
        support_layout.addWidget(self.hot_companies_panel, 1, 1)
        support_layout.addWidget(self.overdue_panel, 2, 0)
        support_layout.addWidget(self.recent_actions_panel, 2, 1)
        support_layout.setColumnStretch(0, 8)
        support_layout.setColumnStretch(1, 5)
        support_layout.setRowStretch(1, 1)
        support_layout.setRowStretch(2, 1)
        root_layout.addLayout(support_layout)

        summary_layout = ResponsiveGridSection(
            min_column_width=300,
            max_columns=3,
            horizontal_spacing=14,
            vertical_spacing=14,
        )

        self.commercial_panel = SurfacePanel(
            "Ticari Ozet",
            "Ikincil ticari KPI'lar ve yonetsel ozetler.",
            surface="dashboard",
            accent="focus",
        )
        self.commercial_table = self._create_summary_table(["Baslik", "Deger"])
        self.commercial_panel.body_layout.addWidget(self.commercial_table)
        self.commercial_panel.setMinimumHeight(332)

        self.pipeline_panel = SurfacePanel(
            "Pipeline Ozeti",
            "Ana asamalara gore firsat dagilimi.",
            surface="dashboard",
        )
        self.pipeline_table = self._create_summary_table(["Asama", "Adet"])
        self.pipeline_panel.body_layout.addWidget(self.pipeline_table)
        self.pipeline_panel.setMinimumHeight(332)

        self.samples_panel = SurfacePanel(
            "Numune Durumu Ozeti",
            "Numune sureclerinin mevcut durum dagilimi.",
            surface="dashboard",
        )
        self.samples_table = self._create_summary_table(["Durum", "Adet"])
        self.samples_panel.body_layout.addWidget(self.samples_table)
        self.samples_panel.setMinimumHeight(332)

        summary_layout.set_items(
            [
                ResponsiveGridItem(self.commercial_panel, role="table", preferred_span=2, min_width=520),
                ResponsiveGridItem(self.pipeline_panel, role="medium", preferred_span=1, min_width=280),
                ResponsiveGridItem(self.samples_panel, role="medium", preferred_span=1, min_width=280),
            ]
        )
        root_layout.addWidget(summary_layout, 1)
        root_layout.addStretch()

        shell_layout.addWidget(scroll_area)

        self.refresh()

    def refresh(self) -> None:
        existing_cards = self.cards_section.findChildren(MetricCard, options=Qt.FindChildOption.FindDirectChildrenOnly)
        for widget in existing_cards:
            widget.deleteLater()

        metrics = get_dashboard_metrics()
        commercial_metrics = get_commercial_metrics()
        pipeline_counts = get_company_pipeline_counts()
        self._populate_pipeline_counts(pipeline_counts)
        cards = [
            ("Toplam Sirket", metrics["total_companies"], "Portfoydeki aktif firma sayisi", "blue"),
            ("Toplam Kisi", metrics["total_contacts"], "Tum karar verici ve ilgili kisiler", "slate"),
            ("Bugunku Aksiyon", metrics["todays_actions"], "Bugun acilan veya tamamlanan temaslar", "indigo"),
            ("Geciken Aksiyon", metrics["delayed_actions"], "Takip bekleyen gecikmis isler", "rose"),
            (
                "Aktif Firsatlar",
                commercial_metrics["active_opportunities"],
                "Aktif pipeline icindeki toplam firsat",
                "blue",
            ),
            (
                "Bekleyen Teklifler",
                commercial_metrics["waiting_offers"],
                "Hazirlaniyor, gonderildi ve gorusulen teklifler",
                "indigo",
            ),
        ]

        self.cards_section.set_items(
            [
                ResponsiveGridItem(MetricCard(title, value, hint, tone), role="compact", preferred_span=1)
                for title, value, hint, tone in cards
            ]
        )

        self._populate_today_table(list_todays_followups())
        self._populate_overdue_table(list_overdue_actions(limit=10))
        self._populate_hot_companies_table(list_hot_companies())
        self._populate_recent_actions_table(list_recent_actions())
        self._populate_smart_alerts(list_smart_followup_alerts())
        self._populate_commercial_table(metrics, commercial_metrics)
        self._populate_pipeline_table(get_pipeline_summary())
        self._populate_samples_table(get_sample_status_summary())

    def _populate_pipeline_counts(self, counts: dict[str, int]) -> None:
        def set_label(key: str, title: str) -> None:
            label = self.pipeline_count_labels.get(key)
            if not label:
                return
            label.setText(f"{title}: {counts.get(key, 0)}")

        set_label("total", "Toplam Şirket")
        set_label("lead", "Lead")
        set_label("contacted", "Contacted")
        set_label("meeting", "Meeting")
        set_label("offer", "Offer")
        set_label("won", "Won")
        set_label("lost", "Lost")

    def _clear_layout(self, layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget:
                widget.deleteLater()
            elif child_layout:
                self._clear_layout(child_layout)

    def _populate_smart_alerts(self, alerts: list[FollowUpAlert]) -> None:
        self._clear_layout(self.alerts_layout)
        if not alerts:
            empty = QLabel("Şu anda dikkat gerektiren kritik takip uyarısı bulunmuyor.")
            empty.setObjectName("SectionSubtitle")
            empty.setWordWrap(True)
            self.alerts_layout.addWidget(empty)
            self.alerts_layout.addStretch(1)
            return

        for alert in alerts:
            row_card = create_toolbar_frame()
            row_layout = QHBoxLayout(row_card)
            row_layout.setContentsMargins(12, 10, 12, 10)
            row_layout.setSpacing(10)

            text_layout = QVBoxLayout()
            text_layout.setContentsMargins(0, 0, 0, 0)
            text_layout.setSpacing(2)

            reason_label = QLabel(alert.rule_label)
            reason_label.setObjectName("SummaryLabel")
            company_label = QLabel(alert.company_name)
            company_label.setObjectName("SummaryValue")
            detail_label = QLabel(alert.description)
            detail_label.setObjectName("SectionSubtitle")
            detail_label.setWordWrap(True)

            text_layout.addWidget(reason_label)
            text_layout.addWidget(company_label)
            text_layout.addWidget(detail_label)

            action_button = QPushButton(alert.primary_action_label)
            set_button_role(action_button, "secondary")
            action_button.clicked.connect(
                lambda _checked=False, current_alert=alert: self._run_alert_action(current_alert)
            )

            row_layout.addLayout(text_layout, 1)
            row_layout.addWidget(action_button, 0, Qt.AlignmentFlag.AlignTop)
            self.alerts_layout.addWidget(row_card)

        self.alerts_layout.addStretch(1)

    def _run_alert_action(self, alert: FollowUpAlert) -> None:
        if alert.primary_action_key == "create_contact":
            dialog = ContactFormDialog(initial_company_id=alert.company_id, parent=self)
            if dialog.exec():
                create_contact(dialog.get_data())
                self.refresh()
            return

        if alert.primary_action_key == "open_ai":
            self._open_company_detail(alert.company_id, focus_tab="ai")
            return

        if alert.primary_action_key == "create_opportunity":
            dialog = OpportunityFormDialog(
                initial_company_id=alert.company_id,
                initial_contact_id=alert.contact_id,
                initial_title=alert.suggested_opportunity_title,
                initial_note=alert.suggested_opportunity_note,
                initial_stage=alert.suggested_opportunity_stage,
                parent=self,
            )
            if dialog.exec():
                create_opportunity(dialog.get_data())
                self.refresh()
            return

        dialog = ActionFormDialog(
            initial_company_id=alert.company_id,
            initial_contact_id=alert.contact_id,
            initial_record_type="Kisi" if alert.contact_id else "Sirket",
            initial_action_type=alert.suggested_action_type,
            initial_channel=alert.suggested_channel,
            initial_note=alert.suggested_note,
            initial_next_action=alert.suggested_next_action,
            initial_next_action_date=alert.suggested_next_action_date,
            parent=self,
        )
        if dialog.exec():
            create_action(dialog.get_data())
            self.refresh()

    def _open_company_detail(self, company_id: int, *, focus_tab: str = "") -> None:
        company = get_company(company_id)
        if not company:
            return
        dialog = CompanyDetailDialog(company, parent=self)
        if focus_tab == "ai":
            dialog.tabs.setCurrentWidget(dialog.ai_analysis_tab)
        dialog.exec()
        self.refresh()

    def _create_action_table(self, headers: list[str], clickable: bool = False) -> QTableWidget:
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        configure_table(table)
        table.setProperty("interactive", clickable)
        if clickable:
            table.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        else:
            table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setMinimumHeight(252)
        return table

    def _create_company_table(self) -> QTableWidget:
        table = self._create_action_table(["Firma", "Oncelik"])
        return table

    def _create_summary_table(self, headers: list[str]) -> QTableWidget:
        table = self._create_action_table(headers)
        table.setMinimumHeight(274)
        return table

    def _set_table_data(
        self,
        table: QTableWidget,
        rows: list[list[str]],
        secondary_columns: set[int] | None = None,
    ) -> None:
        secondary_columns = secondary_columns or set()
        table.clearContents()
        table.setRowCount(len(rows))
        for row_index, values in enumerate(rows):
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                if column in secondary_columns:
                    item.setForeground(QColor("#6f8097"))
                else:
                    item.setForeground(QColor("#172538"))
                table.setItem(row_index, column, item)
        table.resizeColumnsToContents()

    def _populate_today_table(self, actions: list[Action]) -> None:
        if not actions:
            self._set_table_data(self.today_table, [["-", "-", "-", "Bugun planli kayit yok."]], {3})
            return

        rows = [
            [
                action.company.name if action.company else "-",
                action.contact.name if action.contact else "-",
                action.action_type or "-",
                shorten(action.note or action.next_action or "-", width=42, placeholder="..."),
            ]
            for action in actions
        ]
        self._set_table_data(self.today_table, rows, {3})

    def _populate_overdue_table(self, actions: list[Action]) -> None:
        if not actions:
            self._set_table_data(self.overdue_table, [["-", "-", "-", "Gecikmis kayit yok."]], {0, 3})
            return

        rows = [
            [
                action.next_action_date.strftime("%d.%m.%Y") if action.next_action_date else "-",
                action.company.name if action.company else "-",
                action.contact.name if action.contact else "-",
                shorten(action.next_action or action.note or "-", width=36, placeholder="..."),
            ]
            for action in actions
        ]
        self._set_table_data(self.overdue_table, rows, {0, 3})

    def _populate_hot_companies_table(self, companies: list[Company]) -> None:
        if not companies:
            self._set_table_data(self.hot_companies_table, [["Hazir kayit yok", "-"]], {1})
            return

        self.hot_companies_table.setRowCount(len(companies))
        for row, company in enumerate(companies):
            name_item = QTableWidgetItem(company.name)
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            name_item.setForeground(QColor("#172538"))
            self.hot_companies_table.setItem(row, 0, name_item)
            set_priority_table_cell(self.hot_companies_table, row, 1, company.priority)
        self.hot_companies_table.resizeColumnsToContents()

    def _populate_recent_actions_table(self, actions: list[Action]) -> None:
        if not actions:
            self._set_table_data(self.recent_actions_table, [["-", "-", "Son aksiyon yok."]], {0})
            return

        rows = [
            [
                action.created_at.strftime("%d.%m.%Y"),
                action.company.name if action.company else "-",
                action.action_type or "-",
            ]
            for action in actions
        ]
        self._set_table_data(self.recent_actions_table, rows, {0})

    def _populate_commercial_table(
        self,
        base_metrics: dict[str, int],
        metrics: dict[str, int],
    ) -> None:
        rows = [
            ["Yuksek Oncelik", str(base_metrics["high_priority_companies"])],
            ["Aktif Firsat Tutari", self._format_amount(metrics["active_amount"])],
            ["Teklif Verildi", str(metrics["teklif_verildi_count"])],
            ["Kazanilan Firsatlar", str(metrics["won_count"])],
            ["Kaybedilen Firsatlar", str(metrics["lost_count"])],
            ["Kabul Edilen Teklifler", str(metrics["accepted_offers"])],
            ["Testte Olan Numuneler", str(metrics["testing_samples"])],
        ]
        self._set_table_data(self.commercial_table, rows)

    def _populate_pipeline_table(self, summary_rows: list[tuple[str, int]]) -> None:
        self._set_table_data(self.pipeline_table, [[stage, str(count)] for stage, count in summary_rows])

    def _populate_samples_table(self, summary_rows: list[tuple[str, int]]) -> None:
        self._set_table_data(self.samples_table, [[status, str(count)] for status, count in summary_rows])

    def _format_amount(self, value: int | float) -> str:
        return f"{value:,.0f}".replace(",", ".")
