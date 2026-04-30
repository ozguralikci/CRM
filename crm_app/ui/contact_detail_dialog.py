from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from crm_app.models import Contact
from crm_app.services.action_service import create_action
from crm_app.services.contact_service import get_contact
from crm_app.services.contact_intelligence_service import (
    ContactIntelligenceOutput,
    analyze_contact_intelligence,
    has_contact_intelligence_data,
)
from crm_app.services.field_service import (
    ensure_contact_intelligence_fields,
    get_field_values,
    save_field_values,
)
from crm_app.ui.action_form import ActionFormDialog
from crm_app.ui.layout_helpers import ResponsiveGridItem, ResponsiveGridSection, create_scroll_area
from crm_app.ui.list_page_helpers import set_table_empty_state
from crm_app.ui.styles import configure_table, create_page_header, set_button_role
from crm_app.ui.surface_helpers import SurfacePanel, create_compact_stat_card


class ContactDetailDialog(QDialog):
    def __init__(self, contact: Contact, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.contact_id = contact.id
        self.contact = contact
        self.contact_field_values: dict[str, str] = {}
        self.recent_actions = []

        self.setWindowTitle("Kişi Detayı")
        self.setMinimumSize(1040, 760)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 14, 14, 14)
        root_layout.setSpacing(12)

        root_layout.addWidget(
            create_page_header(
                "Kişi Detayı",
                "Kişi profili, iletişim geçmişi ve istihbarat notlarını tek ekranda yönetin.",
            )
        )

        self.summary_card = QFrame()
        self.summary_card.setObjectName("ContentCard")
        summary_layout = QVBoxLayout(self.summary_card)
        summary_layout.setContentsMargins(16, 16, 16, 16)
        summary_layout.setSpacing(10)

        header_row = QHBoxLayout()
        header_row.setSpacing(10)

        title_block = QVBoxLayout()
        title_block.setSpacing(2)
        self.contact_name_label = QLabel("-")
        self.contact_name_label.setObjectName("PageTitle")
        self.contact_role_label = QLabel("-")
        self.contact_role_label.setObjectName("PageSubtitle")
        title_block.addWidget(self.contact_name_label)
        title_block.addWidget(self.contact_role_label)

        self.new_action_button = QPushButton("Aksiyon Oluştur")
        set_button_role(self.new_action_button, "primary")
        self.new_action_button.clicked.connect(self._open_action_form)

        header_row.addLayout(title_block, 1)
        header_row.addWidget(self.new_action_button)
        summary_layout.addLayout(header_row)

        info_grid = ResponsiveGridSection(
            min_column_width=220,
            max_columns=3,
            horizontal_spacing=10,
            vertical_spacing=10,
        )

        self.summary_values: dict[str, QLabel] = {}
        info_cards: list[QFrame] = []
        for index, (key, title) in enumerate(
            [
                ("company", "Şirket"),
                ("title", "Ünvan"),
                ("email", "E-posta"),
                ("phone", "Telefon"),
                ("linkedin", "LinkedIn"),
            ]
        ):
            card, value_label = create_compact_stat_card(title, surface="toolbar")
            info_cards.append(card)
            self.summary_values[key] = value_label

        info_grid.set_items(
            [ResponsiveGridItem(card, role="compact", preferred_span=1, min_width=220) for card in info_cards]
        )
        summary_layout.addWidget(info_grid)
        root_layout.addWidget(self.summary_card)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("WorkspaceTabs")
        self.tabs.setDocumentMode(True)

        self.overview_tab = self._create_overview_tab()
        self.intelligence_tab = self._create_intelligence_tab()
        self.sales_intelligence_tab = self._create_sales_intelligence_tab()
        self.tabs.addTab(self.overview_tab, "Genel Bakış")
        self.tabs.addTab(self.intelligence_tab, "Kişi İstihbarat")
        self.tabs.addTab(self.sales_intelligence_tab, "Satış Zekâsı")
        root_layout.addWidget(self.tabs, 1)

        footer_row = QHBoxLayout()
        footer_row.setContentsMargins(0, 0, 0, 0)
        footer_row.addStretch(1)
        self.close_button = QPushButton("Kapat")
        set_button_role(self.close_button, "secondary")
        self.close_button.clicked.connect(self.accept)
        footer_row.addWidget(self.close_button)
        root_layout.addLayout(footer_row)

        self.refresh_content()

    def _create_overview_tab(self) -> QWidget:
        tab, layout = self._create_scroll_tab(max_content_width=1160)

        self.overview_notes_card = SurfacePanel(
            "İletişim Özeti",
            "Kişinin rolünü ve mevcut iletişim görünürlüğünü hızlıca değerlendirin.",
            surface="toolbar",
        )
        self.overview_notes_label = QLabel("-")
        self.overview_notes_label.setObjectName("SectionSubtitle")
        self.overview_notes_label.setWordWrap(True)
        self.overview_notes_card.body_layout.addWidget(self.overview_notes_label)

        self.actions_card = SurfacePanel(
            "Son Aksiyonlar",
            "Bu kişiyle ilgili son temaslar ve planlanan takip adımları.",
            surface="content",
        )
        self.actions_table = QTableWidget()
        self.actions_table.setColumnCount(4)
        self.actions_table.setHorizontalHeaderLabels(["Tarih", "Şirket", "Aksiyon", "Sonraki Adım"])
        self.actions_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.actions_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.actions_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.actions_table.verticalHeader().setVisible(False)
        self.actions_table.horizontalHeader().setStretchLastSection(True)
        configure_table(self.actions_table)
        self.actions_card.body_layout.addWidget(self.actions_table)

        layout.addWidget(self.overview_notes_card)
        layout.addWidget(self.actions_card)
        layout.addStretch()
        return tab

    def _create_intelligence_tab(self) -> QWidget:
        tab, layout = self._create_scroll_tab(max_content_width=1160)

        meta_card = SurfacePanel(
            "İstihbarat Özeti",
            "Yapısal kişi notlarını sade, tekrar kullanılabilir bir formatta tutun.",
            surface="toolbar",
        )
        meta_grid = ResponsiveGridSection(
            min_column_width=240,
            max_columns=2,
            horizontal_spacing=10,
            vertical_spacing=10,
        )

        tags_card, self.tags_value_label = create_compact_stat_card("Etiketler", surface="toolbar")
        updated_card, self.updated_value_label = create_compact_stat_card(
            "Son Güncelleme Tarihi",
            surface="toolbar",
        )
        meta_grid.set_items(
            [
                ResponsiveGridItem(tags_card, role="compact", preferred_span=1, min_width=240),
                ResponsiveGridItem(updated_card, role="compact", preferred_span=1, min_width=240),
            ]
        )
        meta_card.body_layout.addWidget(meta_grid)

        self.tags_input = QLineEdit()
        self.tags_input.setPlaceholderText("Örn. pazarlıkçı, hızlı karar verir, detaycı")

        self.general_input = QTextEdit()
        self.behavior_input = QTextEdit()
        self.approach_input = QTextEdit()
        self.risk_input = QTextEdit()
        self.free_note_input = QTextEdit()
        editors = [
            self.general_input,
            self.behavior_input,
            self.approach_input,
            self.risk_input,
            self.free_note_input,
        ]
        for editor in editors:
            editor.setMinimumHeight(140)
            editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        grid = ResponsiveGridSection(
            min_column_width=260,
            max_columns=4,
            horizontal_spacing=12,
            vertical_spacing=12,
        )
        intelligence_cards = [
            ResponsiveGridItem(
                self._create_editor_block(
                    "Genel Değerlendirme",
                    "Kişinin genel profili, iletişim tonu ve ilişki seviyesi hakkında kısa bir çerçeve oluşturun.",
                    self.general_input,
                ),
                role="full",
                min_width=640,
            ),
            ResponsiveGridItem(
                self._create_editor_block(
                    "Davranış Analizi",
                    "Karar verme biçimi, iletişim tarzı ve toplantı davranışları gibi gözlemleri toplayın.",
                    self.behavior_input,
                ),
                role="text",
                preferred_span=2,
                min_width=420,
            ),
            ResponsiveGridItem(
                self._create_editor_block(
                    "Ticari Yaklaşım",
                    "Bu kişiyle çalışırken etkili olan satış dili, teklif biçimi ve temas yaklaşımını kaydedin.",
                    self.approach_input,
                ),
                role="text",
                preferred_span=2,
                min_width=420,
            ),
            ResponsiveGridItem(
                self._create_editor_block(
                    "Risk Notları",
                    "Direnç noktaları, geciktirici davranışlar veya ilişki risklerini net biçimde not edin.",
                    self.risk_input,
                ),
                role="text",
                preferred_span=2,
                min_width=420,
            ),
            ResponsiveGridItem(
                self._create_editor_block(
                    "Serbest Not",
                    "Yapıya girmeyen ama ileride işinize yarayacak bağlam notlarını burada tutun.",
                    self.free_note_input,
                ),
                role="full",
                min_width=640,
            ),
        ]
        grid.set_items(intelligence_cards)

        tags_card = SurfacePanel(
            "İstihbarat Etiketleri",
            "Kısa anahtar kelimelerle kişiyi daha hızlı hatırlayın ve iletişim yaklaşımını standardize edin.",
            surface="content",
        )
        tags_card.body_layout.addWidget(self.tags_input)

        actions_card = SurfacePanel(
            "İşlem",
            "Değişiklikleri kaydedin. Kayıt işlemi diğer kişi alanlarını etkilemez.",
            surface="toolbar",
        )
        actions_row = QHBoxLayout()
        actions_row.setContentsMargins(0, 0, 0, 0)
        actions_row.setSpacing(8)
        actions_row.addStretch(1)
        self.refresh_intelligence_button = QPushButton("Yenile")
        set_button_role(self.refresh_intelligence_button, "secondary")
        self.refresh_intelligence_button.clicked.connect(self.refresh_content)
        self.save_intelligence_button = QPushButton("İstihbaratı Kaydet")
        set_button_role(self.save_intelligence_button, "primary")
        self.save_intelligence_button.clicked.connect(self._save_intelligence)
        actions_row.addWidget(self.refresh_intelligence_button)
        actions_row.addWidget(self.save_intelligence_button)
        actions_card.body_layout.addLayout(actions_row)

        layout.addWidget(meta_card)
        layout.addWidget(tags_card)
        layout.addWidget(grid)
        layout.addWidget(actions_card)
        layout.addStretch()
        return tab

    def _create_sales_intelligence_tab(self) -> QWidget:
        tab, layout = self._create_scroll_tab(max_content_width=1160)

        intro_card = SurfacePanel(
            "Satış Zekâsı",
            "Kişi istihbarat notlarından türetilen karar desteği. Bu alan hesaplanır, veritabanına yazılmaz.",
            surface="toolbar",
        )
        self.sales_intelligence_summary = QLabel("Yetersiz veri")
        self.sales_intelligence_summary.setObjectName("SectionSubtitle")
        self.sales_intelligence_summary.setWordWrap(True)
        intro_card.body_layout.addWidget(self.sales_intelligence_summary)

        metrics_grid = ResponsiveGridSection(
            min_column_width=220,
            max_columns=3,
            horizontal_spacing=12,
            vertical_spacing=12,
        )
        self.sales_intelligence_labels: dict[str, QLabel] = {}
        metric_cards: list[QFrame] = []
        for index, (key, title) in enumerate(
            [
                ("profile_type", "Profil Tipi"),
                ("communication_tone", "İletişim Tonu"),
                ("decision_style", "Karar Tipi"),
                ("negotiation_level", "Pazarlık Seviyesi"),
                ("risk_score", "Risk Skoru"),
                ("relationship_strength", "İlişki Gücü"),
            ]
        ):
            card, value_label = create_compact_stat_card(title, surface="toolbar")
            metric_cards.append(card)
            self.sales_intelligence_labels[key] = value_label
        metrics_grid.set_items(
            [ResponsiveGridItem(card, role="compact", preferred_span=1, min_width=220) for card in metric_cards]
        )

        recommendation_card = SurfacePanel(
            "Önerilen Aksiyon",
            "İletişim ve ilerleme biçimini hızla netleştiren hesaplanmış aksiyon önerisi.",
            surface="content",
        )
        self.recommended_action_value = QLabel("Yetersiz veri")
        self.recommended_action_value.setObjectName("SectionTitle")
        self.recommended_action_value.setWordWrap(True)
        recommendation_card.body_layout.addWidget(self.recommended_action_value)

        actions_card = SurfacePanel(
            "İşlem",
            "Satış zekâsını kaydedilmiş kişi istihbarat verisine göre yeniden hesaplayın.",
            surface="toolbar",
        )
        actions_row = QHBoxLayout()
        actions_row.setContentsMargins(0, 0, 0, 0)
        actions_row.setSpacing(8)
        actions_row.addStretch(1)
        self.refresh_sales_intelligence_button = QPushButton("Analizi Yenile")
        set_button_role(self.refresh_sales_intelligence_button, "secondary")
        self.refresh_sales_intelligence_button.clicked.connect(self._populate_sales_intelligence)
        actions_row.addWidget(self.refresh_sales_intelligence_button)
        actions_card.body_layout.addLayout(actions_row)

        layout.addWidget(intro_card)
        layout.addWidget(metrics_grid)
        layout.addWidget(recommendation_card)
        layout.addWidget(actions_card)
        layout.addStretch()
        return tab

    def _create_scroll_tab(self, *, max_content_width: int | None = None) -> tuple[QWidget, QVBoxLayout]:
        tab = QWidget()
        shell_layout = QVBoxLayout(tab)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        scroll_area, _content, content_layout = create_scroll_area(max_content_width=max_content_width)
        content_layout.setContentsMargins(6, 6, 6, 6)
        content_layout.setSpacing(12)
        shell_layout.addWidget(scroll_area)
        return tab, content_layout

    def _create_editor_block(self, title: str, subtitle: str, editor: QTextEdit) -> QFrame:
        card = SurfacePanel(title, subtitle)
        card.body_layout.addWidget(editor)
        return card

    def refresh_content(self) -> None:
        fresh_contact = get_contact(self.contact_id)
        if not fresh_contact:
            return

        self.contact = fresh_contact
        ensure_contact_intelligence_fields()
        self.contact_field_values = get_field_values("contact", self.contact_id)

        self.contact_name_label.setText(self.contact.name)
        company_name = self.contact.company.name if self.contact.company else "-"
        role_text = self.contact.title or "Kayıtlı ünvan yok"
        self.contact_role_label.setText(f"{role_text} | {company_name}")

        self.summary_values["company"].setText(company_name)
        self.summary_values["title"].setText(self.contact.title or "-")
        self.summary_values["email"].setText(self.contact.email or "-")
        self.summary_values["phone"].setText(self.contact.phone or "-")
        self.summary_values["linkedin"].setText(self.contact.linkedin or "-")

        self._populate_overview()
        self._populate_intelligence()
        self._populate_sales_intelligence()

    def _populate_overview(self) -> None:
        self.recent_actions = sorted(self.contact.actions, key=lambda item: item.created_at, reverse=True)
        if self.recent_actions:
            latest_action = self.recent_actions[0]
            summary = (
                f"Son temas {latest_action.created_at.strftime('%d.%m.%Y')} tarihinde "
                f"{latest_action.action_type or 'takip'} olarak kaydedildi."
            )
        else:
            summary = (
                "Henüz aksiyon kaydı yok. İlk teması kaydederek bu kişiyle olan iletişimi izlenebilir hale getirin."
            )
        self.overview_notes_label.setText(summary)

        if not self.recent_actions:
            set_table_empty_state(
                self.actions_table,
                "Henüz kişi bazlı aksiyon yok. İlk aksiyonu oluşturarak iletişim hafızasını başlatın.",
                action_label="Aksiyon Oluştur",
                action_handler=self._open_action_form,
            )
            return

        self.actions_table.clearContents()
        self.actions_table.setRowCount(min(len(self.recent_actions), 6))
        for row, action in enumerate(self.recent_actions[:6]):
            values = [
                action.created_at.strftime("%d.%m.%Y %H:%M"),
                action.company.name if action.company else "-",
                action.action_type or "-",
                action.next_action or "-",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.actions_table.setItem(row, column, item)
        self.actions_table.resizeColumnsToContents()

    def _populate_intelligence(self) -> None:
        self.general_input.setPlainText(self.contact_field_values.get("kisi_genel_degerlendirme", ""))
        self.behavior_input.setPlainText(self.contact_field_values.get("kisi_davranis_analizi", ""))
        self.approach_input.setPlainText(self.contact_field_values.get("kisi_ticari_yaklasim", ""))
        self.risk_input.setPlainText(self.contact_field_values.get("kisi_risk_notlari", ""))
        self.free_note_input.setPlainText(self.contact_field_values.get("kisi_serbest_not", ""))
        self.tags_input.setText(self.contact_field_values.get("kisi_etiketleri", ""))
        tags_text = self.contact_field_values.get("kisi_etiketleri", "").strip()
        self.tags_value_label.setText(tags_text or "-")
        self.updated_value_label.setText(
            self._format_timestamp(self.contact_field_values.get("kisi_istihbarat_guncelleme_tarihi", ""))
        )

    def _save_intelligence(self) -> None:
        updated_values = dict(self.contact_field_values)
        updated_values.update(
            {
                "kisi_genel_degerlendirme": self.general_input.toPlainText().strip(),
                "kisi_davranis_analizi": self.behavior_input.toPlainText().strip(),
                "kisi_ticari_yaklasim": self.approach_input.toPlainText().strip(),
                "kisi_risk_notlari": self.risk_input.toPlainText().strip(),
                "kisi_serbest_not": self.free_note_input.toPlainText().strip(),
                "kisi_etiketleri": self.tags_input.text().strip(),
                "kisi_istihbarat_guncelleme_tarihi": datetime.now().isoformat(timespec="seconds"),
            }
        )
        save_field_values("contact", self.contact_id, updated_values)
        self.contact_field_values = updated_values
        self._populate_intelligence()
        self._populate_sales_intelligence()
        QMessageBox.information(self, "Bilgi", "Kişi istihbarat notları kaydedildi.")

    def _populate_sales_intelligence(self) -> None:
        intelligence_data = self._get_current_intelligence_input()
        if not has_contact_intelligence_data(intelligence_data):
            self.sales_intelligence_summary.setText(
                "Satış zekâsı üretmek için kişi istihbarat alanlarında yeterli veri bulunmuyor."
            )
            for key, label in self.sales_intelligence_labels.items():
                label.setText("Yetersiz veri" if key != "risk_score" else "-")
                if key == "risk_score":
                    label.setStyleSheet("color: #6f8097;")
            self.recommended_action_value.setText("Yetersiz veri")
            return

        output = analyze_contact_intelligence(intelligence_data)
        self.sales_intelligence_summary.setText(
            "Yapısal notlara göre iletişim profili, risk görünümü ve önerilen satış hamlesi hesaplandı."
        )
        self._apply_sales_intelligence_output(output)

    def _get_current_intelligence_input(self) -> dict[str, str]:
        return {
            "kisi_genel_degerlendirme": self.general_input.toPlainText().strip(),
            "kisi_davranis_analizi": self.behavior_input.toPlainText().strip(),
            "kisi_ticari_yaklasim": self.approach_input.toPlainText().strip(),
            "kisi_risk_notlari": self.risk_input.toPlainText().strip(),
            "kisi_etiketleri": self.tags_input.text().strip(),
        }

    def _apply_sales_intelligence_output(self, output: ContactIntelligenceOutput) -> None:
        self.sales_intelligence_labels["profile_type"].setText(output.profile_type)
        self.sales_intelligence_labels["communication_tone"].setText(output.communication_tone)
        self.sales_intelligence_labels["decision_style"].setText(output.decision_style)
        self.sales_intelligence_labels["negotiation_level"].setText(output.negotiation_level)
        self.sales_intelligence_labels["relationship_strength"].setText(output.relationship_strength)
        risk_label = self.sales_intelligence_labels["risk_score"]
        risk_label.setText(str(output.risk_score))
        if output.risk_score > 60:
            risk_label.setStyleSheet("color: #c2410c;")
        elif output.risk_score >= 30:
            risk_label.setStyleSheet("color: #b45309;")
        else:
            risk_label.setStyleSheet("color: #15803d;")
        self.recommended_action_value.setText(output.recommended_action)

    def _open_action_form(self) -> None:
        dialog = ActionFormDialog(
            initial_company_id=self.contact.company_id,
            initial_contact_id=self.contact.id,
            initial_record_type="Kisi",
            initial_action_type="Arama",
            initial_channel="Telefon",
            initial_next_action="Kişiyle sonraki teması planla",
            parent=self,
        )
        if dialog.exec():
            create_action(dialog.get_data())
            self.refresh_content()
            QMessageBox.information(self, "Bilgi", "Kişi için aksiyon kaydı oluşturuldu.")

    def _format_timestamp(self, raw_value: str) -> str:
        if not raw_value:
            return "-"
        try:
            timestamp = datetime.fromisoformat(raw_value)
        except ValueError:
            return raw_value
        return timestamp.strftime("%d.%m.%Y %H:%M")
