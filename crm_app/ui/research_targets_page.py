from __future__ import annotations

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

from crm_app.models.research_target import ResearchTarget
from crm_app.services.research_target_service import (
    basic_duplicate_check,
    create_research_target,
    get_research_target,
    list_research_targets,
    update_research_target,
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

        edit_btn = QPushButton("Duzenle")
        set_button_role(edit_btn, "secondary")
        edit_btn.clicked.connect(self._edit_selected)

        rl.addWidget(detail_title)
        rl.addWidget(self.detail_body, 1)
        rl.addWidget(edit_btn)

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

    def refresh_table(self) -> None:
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
        if len(self._rows) == 1:
            self.table.selectRow(0)

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
            lines.append("• Özet neden üretilemedi (kurallar eşleşmedi veya veri çok seyrek).")
        return lines

    def _build_rules_based_preview_block(self, t: ResearchTarget) -> list[str]:
        cfg = self._get_scoring_config()
        if cfg is None:
            return [
                "Konfigürasyon dosyası yüklenemedi veya PyYAML eksik; kural tabanlı önizleme kullanılamıyor.",
                "(Uygulama çalışmaya devam eder.)",
            ]
        if compute_fit_score is None:
            return ["Skor önizlemesi hesaplanamadı."]
        try:
            result = compute_fit_score(t, cfg)
        except Exception:
            return ["Skor önizlemesi hesaplanamadı."]

        score_v = result.get("score")
        conf_v = result.get("confidence")
        cat_v = result.get("category")
        rec_v = result.get("recommendation")
        rv = result.get("breakdown")
        ruleset = rv.get("ruleset_version") if isinstance(rv, dict) else "?"

        block = [
            f"Önizleme skoru: {score_v} / 100   |   Güven: {conf_v}%",
            f"Kategori: {cat_v}",
            f"Öneri: {rec_v}",
            f"(Kural seti: {ruleset} — veritabanına yazılmaz; tablodaki Skor kayıtlı değerdir.)",
            "",
            "Öne çıkan nedenler:",
            *self._top_reason_lines_tr(result, limit=5),
        ]
        return block

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
            return
        self._populate_detail(row)

    def _populate_detail(self, row: int) -> None:
        if row < 0 or row >= len(self._rows):
            self.detail_body.clear()
            return
        t = self._rows[row]
        comment, suggestion = self._build_fit_comment(t)
        sk = (t.status or "new").strip().lower()
        status_tr = self._status_label_tr(sk)
        lines = [
            "=== Genel ===",
            f"Firma: {t.name}",
            f"Web: {t.website or '-'}",
            f"LinkedIn: {t.linkedin_company_url or '-'}",
            f"Konum: {t.city or '-'}, {t.country or '-'}",
            f"Sektor: {t.sector or '-'}",
            f"Firma tipi: {t.company_type or '-'}",
            f"Uretim yapisi: {t.production_structure or '-'}",
            f"Uygunluk skoru: {t.fit_score}  |  Guven: {t.confidence:.1f}",
            f"Durum: {status_tr}",
            "",
            "=== Uygunluk degerlendirmesi ===",
            comment,
            "",
            "=== Sonraki adim ===",
            suggestion,
            "",
            "=== Kural Tabanlı Skor Önizlemesi ===",
            *self._build_rules_based_preview_block(t),
            "",
            "=== Urun uyumu sinyalleri ===",
            t.product_fit_signals or "-",
            "",
            "=== Notlar ===",
            t.notes or "-",
        ]
        self.detail_body.setPlainText("\n".join(lines))

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
