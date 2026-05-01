from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QSpinBox,
    QDoubleSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from crm_app.database.session import get_session
from crm_app.models.research_target import ResearchTarget
from crm_app.services.research_target_service import (
    basic_duplicate_check,
    create_research_target,
    get_research_target,
    list_research_targets,
    update_research_target,
    update_research_target_scores,
)
from crm_app.ui.list_page_helpers import set_table_empty_state
from crm_app.ui.styles import (
    apply_shadow,
    configure_table,
    create_page_header,
    create_toolbar_frame,
    set_button_role,
    style_dialog_buttons,
)

try:
    from crm_app.scoring.surlas_scoring_v1 import compute_fit_score, load_scoring_config
except ImportError:
    compute_fit_score = None  # type: ignore[misc, assignment]
    load_scoring_config = None  # type: ignore[misc, assignment]


class ResearchTargetDialog(QDialog):
    def __init__(self, target: ResearchTarget | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Yeni Hedef" if target is None else "Hedefi Duzenle")
        self.setMinimumWidth(560)
        self._target_id = target.id if target else None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header = QFrame()
        header.setObjectName("DialogCard")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(18, 18, 18, 18)
        hl.setSpacing(6)
        apply_shadow(header, blur=14, y_offset=2, alpha=10)
        title = QLabel("Hedef Firma")
        title.setObjectName("DialogTitle")
        subtitle = QLabel("Arastirma havuzuna manuel kayit ekleyin veya guncelleyin.")
        subtitle.setObjectName("DialogSubtitle")
        subtitle.setWordWrap(True)
        hl.addWidget(title)
        hl.addWidget(subtitle)

        form_card = QFrame()
        form_card.setObjectName("DialogCard")
        fl = QFormLayout(form_card)
        fl.setHorizontalSpacing(14)
        fl.setVerticalSpacing(10)

        self.name_input = QLineEdit(target.name if target else "")
        self.website_input = QLineEdit(target.website if target else "")
        self.linkedin_input = QLineEdit(target.linkedin_company_url if target else "")
        self.country_input = QLineEdit(target.country if target else "")
        self.city_input = QLineEdit(target.city if target else "")
        self.sector_input = QLineEdit(target.sector if target else "")
        self.company_type_input = QLineEdit(target.company_type if target else "")
        self.production_input = QLineEdit(target.production_structure if target else "")
        self.signals_input = QTextEdit(target.product_fit_signals if target else "")
        self.signals_input.setMinimumHeight(72)
        self.fit_score_input = QSpinBox()
        self.fit_score_input.setRange(0, 100)
        self.fit_score_input.setValue(target.fit_score if target else 0)
        self.confidence_input = QDoubleSpinBox()
        self.confidence_input.setRange(0.0, 100.0)
        self.confidence_input.setDecimals(1)
        self.confidence_input.setValue(float(target.confidence) if target else 0.0)
        self.status_input = QComboBox()
        for s in ["new", "researching", "qualified", "paused", "rejected"]:
            self.status_input.addItem(s, s)
        if target:
            ix = self.status_input.findData(target.status or "new")
            if ix >= 0:
                self.status_input.setCurrentIndex(ix)
        self.notes_input = QTextEdit(target.notes if target else "")
        self.notes_input.setMinimumHeight(88)

        fl.addRow("Firma Adi", self.name_input)
        fl.addRow("Web Sitesi", self.website_input)
        fl.addRow("LinkedIn (sirket)", self.linkedin_input)
        fl.addRow("Ulke", self.country_input)
        fl.addRow("Sehir", self.city_input)
        fl.addRow("Sektor", self.sector_input)
        fl.addRow("Firma Tipi", self.company_type_input)
        fl.addRow("Uretim Yapisi", self.production_input)
        fl.addRow("Urun Uyumu Sinyalleri", self.signals_input)
        fl.addRow("Uygunluk Skoru", self.fit_score_input)
        fl.addRow("Guven", self.confidence_input)
        fl.addRow("Durum", self.status_input)
        fl.addRow("Notlar", self.notes_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        style_dialog_buttons(buttons)

        footer = QFrame()
        footer.setObjectName("DialogCard")
        fl2 = QHBoxLayout(footer)
        fl2.setContentsMargins(16, 12, 16, 12)
        fl2.addStretch()
        fl2.addWidget(buttons)

        layout.addWidget(header)
        layout.addWidget(form_card, 1)
        layout.addWidget(footer)

    def _on_save(self) -> None:
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "Eksik", "Firma adi zorunludur.")
            return

        data = self.get_data()
        dupes = basic_duplicate_check(
            name=data["name"],
            website=data["website"],
            linkedin_company_url=data["linkedin_company_url"],
            exclude_id=self._target_id,
        )
        if dupes:
            names = ", ".join(d.name for d in dupes[:5])
            more = f" (+{len(dupes) - 5} daha)" if len(dupes) > 5 else ""
            answer = QMessageBox.question(
                self,
                "Benzer Kayit",
                f"Benzer kayitlar bulundu: {names}{more}\n\nYine de kaydetmek istiyor musunuz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        self.accept()

    def get_data(self) -> dict[str, Any]:
        return {
            "name": self.name_input.text().strip(),
            "website": self.website_input.text().strip(),
            "linkedin_company_url": self.linkedin_input.text().strip(),
            "country": self.country_input.text().strip(),
            "city": self.city_input.text().strip(),
            "sector": self.sector_input.text().strip(),
            "company_type": self.company_type_input.text().strip(),
            "production_structure": self.production_input.text().strip(),
            "product_fit_signals": self.signals_input.toPlainText().strip(),
            "fit_score": self.fit_score_input.value(),
            "confidence": float(self.confidence_input.value()),
            "status": str(self.status_input.currentData() or "new"),
            "notes": self.notes_input.toPlainText().strip(),
        }


class ResearchTargetsPage(QWidget):
    TABLE_HEADERS = [
        "Firma",
        "Sehir",
        "Ulke",
        "Sektor",
        "Skor",
        "Guven",
        "Durum",
        "Guncelleme",
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[ResearchTarget] = []
        self._scoring_config_loaded: bool = False
        self._scoring_config: dict[str, Any] | None = None
        self._current_breakdown_for_dialog: dict[str, Any] | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(12)

        root.addWidget(
            create_page_header(
                "Arastirma Merkezi",
                "Hedef firma havuzunu olusturun, siniflandirin ve onceliklendirin.",
            )
        )

        metrics_row = QHBoxLayout()
        metrics_row.setContentsMargins(0, 0, 0, 0)
        metrics_row.setSpacing(10)

        self.metric_total = self._create_metric_chip("Toplam Hedef", "0", tone="slate")
        self.metric_high = self._create_metric_chip("Yuksek Potansiyel", "0", tone="blue")
        self.metric_untouched = self._create_metric_chip("Temas Edilmemis", "0", tone="amber")
        self.metric_pending = self._create_metric_chip("Aksiyon Bekleyen", "0", tone="indigo")

        metrics_row.addWidget(self.metric_total["card"], 1)
        metrics_row.addWidget(self.metric_high["card"], 1)
        metrics_row.addWidget(self.metric_untouched["card"], 1)
        metrics_row.addWidget(self.metric_pending["card"], 1)

        filter_bar = create_toolbar_frame()
        filter_bar.setProperty("header_role", "summary")
        apply_shadow(filter_bar, blur=12, y_offset=2, alpha=8)
        filter_layout = QHBoxLayout(filter_bar)
        filter_layout.setContentsMargins(12, 10, 12, 10)
        filter_layout.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Firma, sehir, web veya LinkedIn ile ara...")
        self.country_filter = QLineEdit()
        self.country_filter.setPlaceholderText("Ulke filtresi")
        self.sector_filter = QLineEdit()
        self.sector_filter.setPlaceholderText("Sektor filtresi")
        self.status_filter = QComboBox()
        self.status_filter.addItem("Durum: Tum", "")
        for s in ["new", "researching", "qualified", "paused", "rejected"]:
            self.status_filter.addItem(self._status_label_tr(s), s)

        refresh_btn = QPushButton("Yenile")
        set_button_role(refresh_btn, "ghost")
        refresh_btn.clicked.connect(self.refresh_table)

        self.search_input.textChanged.connect(self.refresh_table)
        self.country_filter.textChanged.connect(self.refresh_table)
        self.sector_filter.textChanged.connect(self.refresh_table)
        self.status_filter.currentIndexChanged.connect(self.refresh_table)

        filter_layout.addWidget(self.search_input, 2)
        filter_layout.addWidget(self.country_filter, 1)
        filter_layout.addWidget(self.sector_filter, 1)
        filter_layout.addWidget(self.status_filter, 1)
        filter_layout.addWidget(refresh_btn, 0)

        add_btn = QPushButton("Yeni Hedef Ekle")
        set_button_role(add_btn, "primary")
        add_btn.clicked.connect(self.add_target)

        top_actions = QHBoxLayout()
        top_actions.setContentsMargins(0, 0, 0, 0)
        top_actions.addStretch(1)
        top_actions.addWidget(add_btn)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        left_wrap = QFrame()
        left_wrap.setObjectName("PageFrame")
        left_layout = QVBoxLayout(left_wrap)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        self.table = QTableWidget(0, len(self.TABLE_HEADERS))
        self.table.setHorizontalHeaderLabels(self.TABLE_HEADERS)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        configure_table(self.table)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            """
            QTableWidget::item:hover {
                background-color: #eef3f9;
            }
            """
        )
        self.table.itemClicked.connect(self._on_item_clicked)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._edit_selected)

        left_layout.addWidget(self.table)

        right_wrap = QFrame()
        right_wrap.setObjectName("SidebarPanel")
        right_wrap.setMinimumWidth(320)
        rl = QVBoxLayout(right_wrap)
        rl.setContentsMargins(12, 12, 12, 12)
        rl.setSpacing(10)

        detail_title = QLabel("Hedef Detayi")
        detail_title.setObjectName("SectionTitle")
        self.detail_body = QTextEdit()
        self.detail_body.setReadOnly(True)
        self.detail_body.setPlaceholderText("Tablodan bir hedef secin.")
        self.detail_body.setMinimumHeight(280)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(8)
        self.save_score_btn = QPushButton("Skoru Kaydet")
        set_button_role(self.save_score_btn, "secondary")
        self.save_score_btn.setEnabled(False)
        self.save_score_btn.setToolTip("Analiz için sektör ve ürün sinyali girin")
        self.save_score_btn.clicked.connect(self._save_preview_score)
        btn_row.addWidget(self.save_score_btn)
        self.detail_breakdown_btn = QPushButton("Detayı gör")
        set_button_role(self.detail_breakdown_btn, "secondary")
        self.detail_breakdown_btn.setEnabled(False)
        self.detail_breakdown_btn.clicked.connect(self._show_breakdown_detail_dialog)
        btn_row.addWidget(self.detail_breakdown_btn)
        btn_row.addStretch(1)
        edit_btn = QPushButton("Duzenle")
        set_button_role(edit_btn, "secondary")
        edit_btn.clicked.connect(self._edit_selected)
        btn_row.addWidget(edit_btn)

        rl.addWidget(detail_title)
        rl.addWidget(self.detail_body, 1)
        rl.addLayout(btn_row)

        splitter.addWidget(left_wrap)
        splitter.addWidget(right_wrap)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        root.addLayout(metrics_row)
        root.addWidget(filter_bar)
        root.addLayout(top_actions)
        root.addWidget(splitter, 1)

        self.refresh_table()

    def _create_metric_chip(self, title: str, value: str, *, tone: str) -> dict[str, Any]:
        card = QFrame()
        card.setObjectName("MetricCard")
        card.setProperty("tone", tone)
        card.setMinimumHeight(92)
        apply_shadow(card, blur=10, y_offset=1, alpha=6)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("MetricTitle")
        value_label = QLabel(value)
        value_label.setObjectName("MetricValue")
        hint_label = QLabel("Filtrelenmis liste")
        hint_label.setObjectName("MetricHint")
        hint_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(hint_label)
        return {"card": card, "value": value_label}

    def refresh_table(self, *, preserve_target_id: int | None = None) -> None:
        self._rows = list_research_targets(
            search=self.search_input.text().strip(),
            status=str(self.status_filter.currentData() or ""),
            country=self.country_filter.text().strip(),
            sector=self.sector_filter.text().strip(),
        )
        self._update_metrics()
        if not self._rows:
            set_table_empty_state(
                self.table,
                "Hedef firma eklemek icin sag ustteki Yeni Hedef Ekle dugmesini kullanin.\n"
                "Filtreler aktifse sonuclari daraltmis olabilirsiniz; filtreleri temizleyip yenileyin.",
                action_label="Yeni Hedef Ekle",
                action_handler=self.add_target,
            )
            self.detail_body.clear()
            self.save_score_btn.setEnabled(False)
            self.detail_breakdown_btn.setEnabled(False)
            self._current_breakdown_for_dialog = None
            return

        self.table.clearSpans()
        self.table.setRowCount(len(self._rows))
        for row, t in enumerate(self._rows):
            score = int(t.fit_score or 0)
            status_key = (t.status or "new").strip().lower()
            status_display = self._format_status_cell(status_key)

            values = [
                t.name,
                t.city or "-",
                t.country or "-",
                t.sector or "-",
                str(score),
                f"{t.confidence:.1f}",
                status_display,
                t.updated_at.strftime("%d.%m.%Y %H:%M") if t.updated_at else "-",
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                if col == 4:
                    bg, fg = self._score_colors(score)
                    item.setBackground(bg)
                    item.setForeground(fg)
                elif col == 6:
                    item.setForeground(self._status_fg(status_key))
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()
        self.detail_body.clear()
        pid = preserve_target_id
        if pid is None and len(self._rows) == 1:
            pid = self._rows[0].id
        if pid is not None:
            idx = next((i for i, x in enumerate(self._rows) if x.id == pid), None)
            if idx is not None:
                self.table.selectRow(idx)
                self._populate_detail(idx)
        self._sync_save_score_button()
        self._sync_detail_breakdown_button()

    def _sync_save_score_button(self) -> None:
        row = self._current_row_index()
        ok = row is not None and 0 <= row < len(self._rows)
        if ok:
            ok = self._has_minimum_fields_for_score_save(self._rows[row])
        self.save_score_btn.setEnabled(ok)

    def _panel_score_band_label(self, score: int) -> str:
        s = max(0, min(100, int(score)))
        if s <= 40:
            return "Zayıf"
        if s <= 70:
            return "Orta"
        if s < 85:
            return "İyi"
        return "Sıcak"

    def _has_minimum_fields_for_score_save(self, t: ResearchTarget) -> bool:
        return bool((t.sector or "").strip()) and len((t.product_fit_signals or "").strip()) >= 12

    def _sync_detail_breakdown_button(self) -> None:
        row = self._current_row_index()
        self._current_breakdown_for_dialog = None
        if row is None or row < 0 or row >= len(self._rows):
            self.detail_breakdown_btn.setEnabled(False)
            return
        t = self._rows[row]
        raw = (getattr(t, "rules_score_breakdown", None) or "").strip()
        if not raw:
            self.detail_breakdown_btn.setEnabled(False)
            return
        try:
            self._current_breakdown_for_dialog = json.loads(raw)
            self.detail_breakdown_btn.setEnabled(True)
        except json.JSONDecodeError:
            self.detail_breakdown_btn.setEnabled(False)

    def _save_preview_score(self) -> None:
        row = self._current_row_index()
        if row is None or row < 0 or row >= len(self._rows):
            return
        t = self._rows[row]
        target_id = t.id
        db_score = int(t.fit_score or 0)
        db_conf = float(t.confidence or 0.0)

        cfg = self._get_scoring_config()
        if cfg is None or compute_fit_score is None:
            QMessageBox.warning(
                self,
                "Skor",
                "Skor hesaplanamadi; yapilandirma yuklenemedi veya PyYAML eksik.",
            )
            return

        try:
            preview = compute_fit_score(t, cfg)
        except Exception as exc:
            QMessageBox.critical(self, "Skor", f"Skor hesaplanamadi:\n{exc}")
            return

        new_score = int(preview.get("score", 0))
        new_conf = float(preview.get("confidence", 0))

        detail_msg = (
            f"Mevcut skor (veritabani): {db_score}  |  Guven: {db_conf:.1f}\n"
            f"Yeni skor (onizleme): {new_score}  |  Guven: {new_conf:.1f}\n\n"
            "Bu işlem mevcut skoru güncelleyecek. Devam etmek istiyor musunuz?"
        )
        answer = QMessageBox.question(
            self,
            "Skoru Kaydet",
            detail_msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            preview2 = compute_fit_score(t, cfg)
            new_score = int(preview2.get("score", 0))
            new_conf = float(preview2.get("confidence", 0))
        except Exception as exc:
            QMessageBox.critical(self, "Skor", f"Skor tekrar hesaplanamadi:\n{exc}")
            return

        bd_inner = preview2.get("breakdown")
        if not isinstance(bd_inner, dict):
            bd_inner = {}
        try:
            breakdown_json = json.dumps(bd_inner, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            QMessageBox.critical(self, "Skor", f"Analiz verisi hazirlanamadi:\n{exc}")
            return

        rules_version = str(bd_inner.get("ruleset_version") or "")
        saved_at = datetime.utcnow()

        session = get_session()
        try:
            update_research_target_scores(
                session,
                target_id,
                new_score,
                new_conf,
                breakdown_json=breakdown_json,
                rules_version=rules_version or None,
                updated_at=saved_at,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Skor", f"Kaydedilemedi:\n{exc}")
            return
        finally:
            session.close()

        self.refresh_table(preserve_target_id=target_id)

    def _on_item_clicked(self, _item: QTableWidgetItem) -> None:
        row = self._current_row_index()
        if row is None:
            return
        if row < 0 or row >= len(self._rows):
            return
        self._populate_detail(row)

    def _update_metrics(self) -> None:
        total = len(self._rows)
        high = sum(1 for t in self._rows if int(t.fit_score or 0) > 70)
        untouched = sum(1 for t in self._rows if (t.status or "").strip().lower() == "new")
        pending = sum(
            1
            for t in self._rows
            if (t.status or "").strip().lower() in {"researching", "paused"}
            or (
                (t.status or "").strip().lower() == "new"
                and not (t.notes or "").strip()
                and not (t.product_fit_signals or "").strip()
            )
        )
        self.metric_total["value"].setText(str(total))
        self.metric_high["value"].setText(str(high))
        self.metric_untouched["value"].setText(str(untouched))
        self.metric_pending["value"].setText(str(pending))

    def _score_colors(self, score: int) -> tuple[QColor, QColor]:
        if score >= 70:
            return QColor("#ecfdf3"), QColor("#166534")
        if score > 40:
            return QColor("#fffbeb"), QColor("#92400e")
        return QColor("#fef2f2"), QColor("#991b1b")

    def _status_fg(self, status_key: str) -> QColor:
        bucket = self._status_bucket(status_key)
        if bucket == "green":
            return QColor("#15803d")
        if bucket == "yellow":
            return QColor("#b45309")
        return QColor("#b91c1c")

    def _status_bucket(self, status_key: str) -> str:
        if status_key in {"qualified"}:
            return "green"
        if status_key in {"new", "researching", "paused"}:
            return "yellow"
        return "red"

    def _status_label_tr(self, status_key: str) -> str:
        mapping = {
            "new": "Yeni",
            "researching": "Araştırılıyor",
            "qualified": "Uygun",
            "rejected": "Düşük",
            "paused": "Beklemede",
        }
        return mapping.get(status_key, status_key)

    def _format_status_cell(self, status_key: str) -> str:
        bucket = self._status_bucket(status_key)
        prefix = {"yellow": "[Yeni]", "green": "[Uygun]", "red": "[Dusuk]"}.get(bucket, "[Dusuk]")
        label = self._status_label_tr(status_key)
        return f"{prefix} {label}"

    def _build_fit_comment(self, t: ResearchTarget) -> tuple[str, str]:
        score = int(t.fit_score or 0)
        missing_web = not (t.website or "").strip()
        missing_li = not (t.linkedin_company_url or "").strip()
        thin_signals = len((t.product_fit_signals or "").strip()) < 12
        missing_sector = not (t.sector or "").strip()

        static_gap_msg = "Veri eksik. Website, sektör ve ürün uyumu sinyalleri eklenmeli."
        if score == 0 or missing_web or missing_sector or thin_signals:
            return static_gap_msg, static_gap_msg

        if missing_li:
            headline = "LinkedIn sirket linki eksik; karar verici haritalama zorlasir."
        elif score >= 70:
            headline = "Skor yuksek gorunuyor; bir sonraki adim netlestirme ve karar verici bulma."
        elif score > 40:
            headline = "Orta potansiyel; kanit kaynaklarini artirin ve durumu daraltin."
        else:
            headline = "Dusuk potansiyel gorunumu; dislamadan once 2-3 kanit kaydi ekleyin."

        tips: list[str] = []
        if missing_li:
            tips.append("- LinkedIn sirket URL'sini ekleyin.")
        if score >= 70:
            tips.append("- Kaynak notlari ekleyin ve durumu daraltin (Uygun / Dusuk).")
        elif score > 40:
            tips.append("- Sektor ve urun uyumu sinyallerini guclendirin.")
        else:
            tips.append("- En az iki kanit kaynagi ekleyin; gerekiyorsa statuyu Dusuk olarak kapatin.")

        return headline, "\n".join(tips)

    def _get_scoring_config(self) -> dict[str, Any] | None:
        if self._scoring_config_loaded:
            return self._scoring_config
        self._scoring_config_loaded = True
        if load_scoring_config is None:
            self._scoring_config = None
            return None
        try:
            self._scoring_config = load_scoring_config()
        except Exception:
            self._scoring_config = None
        return self._scoring_config

    def _collect_rules_based_reasons_tr(self, result: dict[str, Any]) -> list[tuple[int, str]]:
        bd = result.get("breakdown")
        if not isinstance(bd, dict):
            return []
        ranked: list[tuple[int, str]] = []
        comps = bd.get("components")
        if isinstance(comps, dict):
            sector = comps.get("sector")
            if isinstance(sector, dict):
                if sector.get("exclude_hit"):
                    cap = sector.get("cap_final_score")
                    cap_txt = f", genel skor tavanı ~{cap}" if cap is not None else ""
                    pat = sector.get("matched_pattern") or "?"
                    ranked.append(
                        (
                            50,
                            f"Sektör dışlama kuralı tetiklendi ({pat}){cap_txt}.",
                        )
                    )
                else:
                    pts = int(sector.get("points") or 0)
                    tier = sector.get("matched_tier") or "bilinmiyor"
                    if pts > 0:
                        ranked.append((pts + 5, f"Sektör uyumu ({tier}): +{pts} puan."))
                    elif not (sector.get("raw_sector") or "").strip():
                        ranked.append((25, "Sektör alanı boş; sektör puanı alınamadı."))

            prod = comps.get("product_signals")
            if isinstance(prod, dict):
                for g in prod.get("groups") or []:
                    if not isinstance(g, dict):
                        continue
                    gp = int(g.get("points") or 0)
                    if gp <= 0:
                        continue
                    gid = g.get("id") or "grup"
                    kws = g.get("keywords_hit") or []
                    kw_txt = f" ({', '.join(str(x) for x in kws[:3])})" if kws else ""
                    ranked.append((gp + 2, f"Ürün uyumu ({gid}){kw_txt}: +{gp} puan."))
                neg = int(prod.get("negative_subtract") or 0)
                if neg > 0:
                    nh = prod.get("negative_hits") or []
                    htxt = ", ".join(str(x) for x in nh[:4])
                    ranked.append((neg + 8, f"Riskli anahtar kelimeler ({htxt}): −{neg} puan."))

            op = comps.get("operational")
            if isinstance(op, dict):
                for m in op.get("matched") or []:
                    if not isinstance(m, dict):
                        continue
                    pts = int(m.get("points") or 0)
                    if pts <= 0:
                        continue
                    lbl = m.get("type") or "alan"
                    pat = m.get("pattern") or ""
                    ranked.append((pts + 1, f"Operasyonel uygunluk ({lbl}: {pat}): +{pts} puan."))

            ev = comps.get("evidence")
            if isinstance(ev, dict):
                for it in ev.get("items") or []:
                    if not isinstance(it, dict):
                        continue
                    pts = int(it.get("points") or 0)
                    if pts <= 0:
                        continue
                    fld = it.get("field") or "alan"
                    ranked.append((pts, f"Veri kanıtı ({fld}): +{pts} puan."))

        pens = bd.get("penalties")
        if isinstance(pens, dict):
            for ln in pens.get("lines") or []:
                if not isinstance(ln, dict):
                    continue
                code = str(ln.get("code") or "")
                pts = int(ln.get("points") or 0)
                mag = abs(pts)
                if code == "missing_website":
                    msg = f"Web sitesi eksik: −{pts} puan cezası."
                elif code == "missing_sector":
                    msg = f"Sektör bilgisi eksik: −{pts} puan cezası."
                elif code == "missing_or_thin_signals":
                    msg = f"Ürün uyumu metni eksik veya çok kısa: −{pts} puan cezası."
                elif code == "critical_bundle_2of3":
                    msg = f"Birden fazla kritik alan eksik (paket cezası): −{pts} puan."
                else:
                    msg = f"Cezalandırma ({code}): −{pts} puan."
                ranked.append((mag + 12, msg))

        sums = bd.get("sums")
        if isinstance(sums, dict):
            for cap in sums.get("caps_applied") or []:
                if not isinstance(cap, dict):
                    continue
                reason = str(cap.get("reason") or "")
                cap_v = cap.get("cap")
                if reason == "sector_exclude":
                    ranked.append((45, f"Genel skor tavanı uygulandı (sektör dışlama), üst sınır: {cap_v}."))
                elif reason == "critical_data_bundle":
                    ranked.append((44, f"Kritik veri eksikliği nedeniyle skor tavanı: {cap_v}."))

        ranked.sort(key=lambda x: x[0], reverse=True)
        return ranked

    def _top_reason_lines_tr(self, result: dict[str, Any], *, limit: int = 5) -> list[str]:
        ranked = self._collect_rules_based_reasons_tr(result)
        lines: list[str] = []
        for _, msg in ranked[:limit]:
            lines.append(f"• {msg}")
        if not lines:
            lines.append("• Analiz özeti için sektör ve ürün uyumu alanlarını netleştirin.")
        return lines

    def _skor_analizi_unavailable_lines(self) -> list[str]:
        return [
            "⚠️ Analiz yapılamıyor",
            "",
            "Eksik bilgiler:",
            "- sektör",
            "- ürün uyumu sinyalleri",
            "",
            "Bu alanları doldurarak tekrar deneyin.",
        ]

    def _build_rules_based_preview_block(self, t: ResearchTarget) -> list[str]:
        hdr = ["Durum: Analiz yapılmadı", ""]
        cfg = self._get_scoring_config()
        if cfg is None or compute_fit_score is None:
            return hdr + self._skor_analizi_unavailable_lines()
        try:
            result = compute_fit_score(t, cfg)
        except Exception:
            return hdr + self._skor_analizi_unavailable_lines()

        score_v = int(result.get("score", 0))
        conf_v = result.get("confidence")
        rec_v = result.get("recommendation")
        band = self._panel_score_band_label(score_v)

        if score_v == 0:
            block = hdr + [
                f"🔴 Skor: {score_v} → {band}",
                f"Güven: {conf_v}%",
                f"Özet: {rec_v}",
                "",
                "Kalıcı kayıt için «Skoru Kaydet» (önce sektör ve ürün sinyali tamamlayın).",
                "",
                "Öne çıkan nedenler:",
                *self._top_reason_lines_tr(result, limit=5),
            ]
            return block

        block = hdr + [
            f"Skor: {score_v} → {band}   |   Güven: {conf_v}%",
            f"Öneri: {rec_v}",
            "",
            "Kalıcı kayıt için «Skoru Kaydet».",
            "",
            "Öne çıkan nedenler:",
            *self._top_reason_lines_tr(result, limit=5),
        ]
        return block

    def _build_skor_analizi_section(self, t: ResearchTarget) -> list[str]:
        raw_bd = (getattr(t, "rules_score_breakdown", None) or "").strip()
        if not raw_bd:
            return self._build_rules_based_preview_block(t)
        try:
            bd = json.loads(raw_bd)
        except json.JSONDecodeError:
            return [
                "Durum: Kayıtlı analiz okunamadı",
                "Kayıtlı veri okunamıyor; aşağıda güncel hesaplama gösterilir.",
                "",
                *self._build_rules_based_preview_block(t),
            ]
        if not isinstance(bd, dict):
            return [
                "Durum: Kayıtlı analiz okunamadı",
                "",
                *self._build_rules_based_preview_block(t),
            ]
        fake_result: dict[str, Any] = {"breakdown": bd}
        ver = (getattr(t, "rules_score_version", None) or "").strip() or str(bd.get("ruleset_version") or "-")
        ts = getattr(t, "rules_score_updated_at", None)
        ts_fmt = ts.strftime("%d.%m.%Y %H:%M") if ts else "-"
        sv = int(t.fit_score or 0)
        band = self._panel_score_band_label(sv)
        return [
            "Durum: Kayıtlı analiz",
            f"Sürüm: {ver}  ·  Zaman: {ts_fmt}",
            f"Skor: {sv} → {band}   |   Güven: {float(t.confidence or 0):.1f}",
            "",
            "Öne çıkan nedenler:",
            *self._top_reason_lines_tr(fake_result, limit=5),
            "",
            "Tüm kalemler: «Detayı gör». Güncellemek için «Skoru Kaydet».",
        ]

    def _format_breakdown_detail_text(self, bd: dict[str, Any]) -> str:
        lines: list[str] = []
        rv = bd.get("ruleset_version")
        if rv:
            lines.append(f"Sürüm: {rv}")
        wr = bd.get("weights_reference")
        if isinstance(wr, dict) and wr:
            lines.append("")
            lines.append("Puan üst sınırları")
            lines.append(f"  • Sektör: {wr.get('sector_max', '-')}")
            lines.append(f"  • Ürün sinyalleri: {wr.get('product_max', '-')}")
            lines.append(f"  • Operasyonel: {wr.get('operational_max', '-')}")
            lines.append(f"  • Kanıt / tamlık: {wr.get('evidence_max', '-')}")

        comps = bd.get("components")
        if isinstance(comps, dict):
            sec = comps.get("sector")
            if isinstance(sec, dict):
                lines.append("")
                lines.append("Sektör")
                lines.append(f"  • Ham metin: {sec.get('raw_sector') or '(boş)'}")
                lines.append(f"  • Eşleşme: {sec.get('matched_tier') or '-'} — {sec.get('matched_pattern') or '-'}")
                lines.append(f"  • Puan: {sec.get('points', 0)} / {sec.get('max', '-')}")
                if sec.get("exclude_hit"):
                    lines.append("  • Not: Dışlama kuralı tetiklendi.")

            prod = comps.get("product_signals")
            if isinstance(prod, dict):
                lines.append("")
                lines.append("Ürün uyumu sinyalleri")
                lines.append(f"  • Toplam (tavan öncesi): {prod.get('points_before_cap', prod.get('points', '-'))}")
                lines.append(f"  • Hesaplanan puan: {prod.get('points', '-')}")
                for g in prod.get("groups") or []:
                    if isinstance(g, dict):
                        gh = ", ".join(str(x) for x in (g.get("keywords_hit") or [])[:6])
                        lines.append(f"  • Grup {g.get('id')}: +{g.get('points', 0)} {('— ' + gh) if gh else ''}")
                nh = prod.get("negative_hits") or []
                if nh:
                    lines.append(f"  • Uyarıcı kelimeler: {', '.join(str(x) for x in nh)}")

            op = comps.get("operational")
            if isinstance(op, dict):
                lines.append("")
                lines.append("Operasyonel uygunluk")
                lines.append(f"  • Puan: {op.get('points', 0)} / {op.get('max', '-')}")
                for m in op.get("matched") or []:
                    if isinstance(m, dict):
                        lines.append(
                            f"  • {m.get('type')}: {m.get('pattern')} (+{m.get('points', 0)})"
                        )

            ev = comps.get("evidence")
            if isinstance(ev, dict):
                lines.append("")
                lines.append("Veri kanıtları")
                lines.append(f"  • Toplam: {ev.get('points', 0)} / {ev.get('max', '-')}")
                for it in ev.get("items") or []:
                    if isinstance(it, dict):
                        lines.append(f"  • {it.get('field')}: +{it.get('points', 0)}")

        pens = bd.get("penalties")
        if isinstance(pens, dict):
            lines.append("")
            lines.append("Cezalar ve eksik veri")
            for ln in pens.get("lines") or []:
                if isinstance(ln, dict):
                    lines.append(f"  • {ln.get('code')}: −{ln.get('points', 0)}")
            lines.append(
                f"  • Ceza toplamı (üst sınırlı): {pens.get('capped_total', pens.get('raw_total', '-'))}"
            )

        sums = bd.get("sums")
        if isinstance(sums, dict):
            lines.append("")
            lines.append("Özet")
            lines.append(f"  • Bileşen toplamı: {sums.get('raw_components', '-')}")
            lines.append(f"  • Ceza sonrası (tavan öncesi): {sums.get('after_penalties_uncapped_clamped', '-')}")
            for cap in sums.get("caps_applied") or []:
                if isinstance(cap, dict):
                    lines.append(f"  • Uygulanan tavan: {cap.get('reason')} → {cap.get('cap')}")

        return "\n".join(lines) if lines else "Ayrıntı bulunamadı."

    def _show_breakdown_detail_dialog(self) -> None:
        bd = self._current_breakdown_for_dialog
        if not bd:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Analiz detayı")
        dlg.setMinimumWidth(440)
        dlg.setMinimumHeight(400)
        vl = QVBoxLayout(dlg)
        body = QTextEdit()
        body.setReadOnly(True)
        body.setPlainText(self._format_breakdown_detail_text(bd))
        vl.addWidget(body)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        bb.accepted.connect(dlg.accept)
        vl.addWidget(bb)
        dlg.exec()

    def add_target(self) -> None:
        dialog = ResearchTargetDialog(parent=self)
        if not dialog.exec():
            return
        create_research_target(dialog.get_data())
        self.refresh_table()

    def _current_row_index(self) -> int | None:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return None
        return indexes[0].row()

    def _on_selection_changed(self) -> None:
        row = self._current_row_index()
        if row is None or row < 0 or row >= len(self._rows):
            self.detail_body.clear()
            self._sync_save_score_button()
            self._sync_detail_breakdown_button()
            return
        self._populate_detail(row)
        self._sync_save_score_button()

    def _populate_detail(self, row: int) -> None:
        if row < 0 or row >= len(self._rows):
            self.detail_body.clear()
            self.detail_breakdown_btn.setEnabled(False)
            self._current_breakdown_for_dialog = None
            return
        t = self._rows[row]
        comment, suggestion = self._build_fit_comment(t)
        sk = (t.status or "new").strip().lower()
        status_tr = self._status_label_tr(sk)
        ks = int(t.fit_score or 0)
        lines = [
            "GENEL BİLGİ",
            f"Firma: {t.name}",
            f"Web: {t.website or '-'}",
            f"LinkedIn: {t.linkedin_company_url or '-'}",
            f"Konum: {t.city or '-'}, {t.country or '-'}",
            f"Sektör: {t.sector or '-'}",
            f"Firma tipi: {t.company_type or '-'}",
            f"Üretim yapısı: {t.production_structure or '-'}",
            f"Kayıtlı skor: {ks} → {self._panel_score_band_label(ks)}  |  Güven: {t.confidence:.1f}",
            f"Durum: {status_tr}",
            "",
            "",
            "UYGUNLUK DEĞERLENDİRMESİ",
            comment,
            "",
            "",
            "SONRAKİ ADIM",
            suggestion,
            "",
            "",
            "Bu firmayı analiz etmek için:",
            "1. Sektör gir",
            "2. Ürün uyumu sinyali ekle",
            "3. Skoru Kaydet",
            "",
            "",
            "SKOR ANALİZİ",
            *self._build_skor_analizi_section(t),
            "",
            "",
            "ÜRÜN UYUMU SİNYALLERİ",
            t.product_fit_signals or "-",
            "",
            "",
            "NOTLAR",
            t.notes or "-",
        ]
        self.detail_body.setPlainText("\n".join(lines))
        self._sync_detail_breakdown_button()

    def _edit_selected(self, _item: QTableWidgetItem | None = None) -> None:
        row = self._current_row_index()
        if row is None or row < 0 or row >= len(self._rows):
            return
        tid = self._rows[row].id
        target = get_research_target(tid)
        if not target:
            return
        dialog = ResearchTargetDialog(target=target, parent=self)
        if not dialog.exec():
            return
        update_research_target(tid, dialog.get_data())
        self.refresh_table()
