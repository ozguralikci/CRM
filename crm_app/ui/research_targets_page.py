from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QSpinBox,
    QStackedWidget,
    QDoubleSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from crm_app.database.session import get_session
from crm_app.models.research_target import ResearchTarget
from crm_app.config.ai_settings import effective_openai_model, load_ai_settings
from crm_app.services.ai_analysis_service import (
    OpenAINotActiveError,
    run_ai_analysis_for_target,
    run_ai_suggest_for_dialog,
)
from crm_app.services.research_target_service import (
    basic_duplicate_check,
    create_research_target,
    get_research_target,
    list_research_targets,
    update_research_target,
    update_research_target_ai_analysis,
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


def _fmt_truncate(text: str, max_len: int = 120) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    if len(t) <= max_len:
        return t
    return t[: max_len - 1] + "…"


def _impact_suffix_for_risk(risk: str) -> str:
    low = risk.lower()
    if "fiyat" in low or "rekabet" in low:
        return "marj baskısı ve kayıp teklif riski doğurabilir"
    if "oem" in low or "onay" in low:
        return "satış döngüsü uzayabilir veya teklif reddedilebilir"
    if "tedarik" in low:
        return "giriş için teknik farklılık şart; yoksa süreç tıkanır"
    return "satış görüşmelerinde geri çekilme veya kayıp riski taşır"


def _build_neden_line(data: dict[str, Any]) -> str:
    risks = data.get("risks") if isinstance(data.get("risks"), list) else []
    r0 = str(risks[0]).strip() if risks else ""
    sd = (data.get("sales_difficulty") or "").strip()
    if r0:
        return _fmt_truncate(f"{r0} → {_impact_suffix_for_risk(r0)}", 120)
    if sd:
        head = sd.split("—")[0].strip() if "—" in sd else sd[:60]
        return _fmt_truncate(f"{head} → teklif veya onay aşamasında elenme riski artar", 120)
    return ""


def _build_oneri_line(data: dict[str, Any]) -> str:
    """[decision] → [eylem/rol] → [yöntem] — max 120 char."""
    raw_dec = (data.get("decision") or "").strip()
    d_up = raw_dec.upper()
    fire = "🔥 " if ("TAKİP" in d_up or "TAKIP" in d_up.replace("İ", "I")) else ""

    deps = data.get("departments") if isinstance(data.get("departments"), list) else []
    roles = data.get("target_roles") if isinstance(data.get("target_roles"), list) else []
    role_name = ""
    if roles:
        role_name = str(roles[0]).strip()
    elif deps:
        role_name = str(deps[0]).strip()
    if not role_name:
        role_name = "Satınalma/teknik sorumlu"

    strat = (data.get("sales_strategy") or data.get("sales_approach") or "").strip()
    fm = (data.get("first_message") or "").strip()

    if strat:
        tail = strat.split(";")[0].split(".")[0].strip()
        method = _fmt_truncate(tail, 45) if tail else "teknik ön sorularla temas planla"
    elif fm:
        method = "kısa teknik giriş maili ile talep netleştir"
    else:
        method = "kayıt sinyallerine göre numune veya teknik soru seti hazırla"

    mid = f"{role_name} rolünü doğrula ve hedefle"
    line = f"{fire}{raw_dec or '—'} → {mid} → {method}"
    return _fmt_truncate(line, 120)


def _split_strategy_fragments(text: str) -> list[str]:
    t = (text or "").replace("\n", " ").strip()
    if not t:
        return []
    parts: list[str] = []
    for chunk in t.replace(". ", ";").split(";"):
        c = chunk.strip()
        if c:
            parts.append(c)
    return parts[:3]


def _build_aksiyon_steps(data: dict[str, Any]) -> list[str]:
    steps: list[str] = []
    deps = [str(x).strip() for x in (data.get("departments") or []) if str(x).strip()]
    roles_tr = [str(x).strip() for x in (data.get("target_roles") or []) if str(x).strip()]
    role_hint = deps[0] if deps else (roles_tr[0] if roles_tr else "karar verici")

    strat = (data.get("sales_strategy") or data.get("sales_approach") or "").strip()
    fm = (data.get("first_message") or "").strip()

    steps.append(f"{role_hint} için LinkedIn veya kurumsal hat üzerinden doğru kontağı tespit et")

    if fm:
        steps.append(
            f"Kısa teknik özet içeren mail ile ihtiyacı netleştir (konu: sızdırmazlık / conta uyumu)"
        )
    for frag in _split_strategy_fragments(strat):
        if len(steps) >= 4:
            break
        if frag and frag not in " ".join(steps):
            steps.append(_fmt_truncate(frag, 100))

    steps.append("3 iş günü sonra yanıt yoksa tek cümlelik hatırlatma maili gönder")

    out: list[str] = []
    for s in steps:
        s = s.strip()
        if s and s not in out:
            out.append(s)
        if len(out) >= 4:
            break

    while len(out) < 2:
        out.append("Kayıtta sektör ve ürün sinyalini güncel tut; ardından Skoru Kaydet ile önceliği netleştir")
    return out[:4]


class _PanelAiAnalysisWorker(QThread):
    """Panel «AI Analiz Et» — ağ çağrısı UI thread'ini bloklamaz."""

    finished_ok = Signal(int, dict)
    finished_err = Signal(int, str)

    def __init__(self, target_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tid = target_id

    def run(self) -> None:
        tid = self._tid
        from crm_app.services.ai_analysis_service import format_panel_ai_user_message

        session = get_session()
        try:
            t = session.get(ResearchTarget, tid)
            if t is None:
                self.finished_err.emit(tid, "Hedef kaydı bulunamadı.")
                return
            result = run_ai_analysis_for_target(t)
            self.finished_ok.emit(tid, result)
        except Exception as e:
            self.finished_err.emit(tid, format_panel_ai_user_message(e))
        finally:
            session.close()


class ResearchTargetDialog(QDialog):
    def __init__(self, target: ResearchTarget | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Yeni Hedef" if target is None else "Hedefi Duzenle")
        self.setMinimumWidth(600)
        self._target_id = target.id if target else None
        self._is_new = target is None
        self._ai_suggest_result: dict[str, Any] | None = None

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
        self.notes_input.setMinimumHeight(120)

        tab_basic = QWidget()
        fl_basic = QFormLayout(tab_basic)
        fl_basic.setHorizontalSpacing(14)
        fl_basic.setVerticalSpacing(10)
        fl_basic.addRow("Firma Adi", self.name_input)
        fl_basic.addRow("Web Sitesi", self.website_input)
        fl_basic.addRow("LinkedIn (sirket)", self.linkedin_input)
        fl_basic.addRow("Ulke", self.country_input)
        fl_basic.addRow("Sehir", self.city_input)

        tab_class = QWidget()
        fl_class = QFormLayout(tab_class)
        fl_class.setHorizontalSpacing(14)
        fl_class.setVerticalSpacing(10)
        fl_class.addRow("Sektor", self.sector_input)
        fl_class.addRow("Firma Tipi", self.company_type_input)
        fl_class.addRow("Uretim Yapisi", self.production_input)
        fl_class.addRow("Urun Uyumu Sinyalleri", self.signals_input)
        fl_class.addRow("Uygunluk Skoru", self.fit_score_input)
        fl_class.addRow("Guven", self.confidence_input)
        fl_class.addRow("Durum", self.status_input)

        tab_notes = QWidget()
        notes_layout = QVBoxLayout(tab_notes)
        notes_layout.setContentsMargins(0, 0, 0, 0)
        notes_layout.addWidget(self.notes_input)

        self._tabs = QTabWidget()
        self._tabs.addTab(tab_basic, "Temel Bilgi")
        self._tabs.addTab(tab_class, "Sınıflandırma")
        self._tabs.setCurrentIndex(0)

        self._ai_research_btn: QPushButton | None = None
        self._ai_preview: QTextEdit | None = None
        self._ai_apply_btn: QPushButton | None = None
        if self._is_new:
            tab_ai = QWidget()
            ai_l = QVBoxLayout(tab_ai)
            ai_l.setContentsMargins(0, 6, 0, 0)
            ai_l.setSpacing(8)
            ai_title = QLabel("AI destekli öneri (mock)")
            ai_title.setObjectName("DialogSubtitle")
            self._ai_research_btn = QPushButton("AI ile Araştır ve Analiz Et")
            set_button_role(self._ai_research_btn, "secondary")
            self._ai_research_btn.clicked.connect(self._on_ai_research_clicked)
            self._ai_preview = QTextEdit()
            self._ai_preview.setReadOnly(True)
            self._ai_preview.setMinimumHeight(160)
            self._ai_preview.setPlaceholderText("AI çalıştırıldığında önizleme burada görünür.")
            self._ai_apply_btn = QPushButton("Forma Uygula")
            set_button_role(self._ai_apply_btn, "secondary")
            self._ai_apply_btn.setEnabled(False)
            self._ai_apply_btn.clicked.connect(self._on_apply_ai_to_form)
            ai_l.addWidget(ai_title)
            ai_l.addWidget(self._ai_research_btn)
            ai_l.addWidget(self._ai_preview, 1)
            ai_l.addWidget(self._ai_apply_btn)
            self._tabs.addTab(tab_ai, "AI Analiz")

        self._tabs.addTab(tab_notes, "Notlar")

        tab_shell = QFrame()
        tab_shell.setObjectName("DialogCard")
        tsl = QVBoxLayout(tab_shell)
        tsl.setContentsMargins(12, 12, 12, 12)
        tsl.addWidget(self._tabs)

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
        layout.addWidget(tab_shell, 1)
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

    def get_ai_persistence_fields(self) -> dict[str, Any]:
        """AI calistirildiysa kayit icin alanlar; aksi halde bos (NULL)."""
        if not self._ai_suggest_result:
            return {}
        return {
            "ai_analysis_json": json.dumps(self._ai_suggest_result, ensure_ascii=False),
            "ai_analysis_version": str(self._ai_suggest_result.get("schema_version") or "ai_analysis_v1"),
            "ai_model": "mock",
            "ai_analysis_updated_at": datetime.utcnow(),
        }

    def _dialog_ai_context(self) -> dict[str, Any]:
        return {
            "name": self.name_input.text().strip(),
            "website": self.website_input.text().strip(),
            "linkedin_company_url": self.linkedin_input.text().strip(),
            "country": self.country_input.text().strip(),
            "city": self.city_input.text().strip(),
        }

    def _format_dialog_ai_preview(self, data: dict[str, Any]) -> str:
        lines: list[str] = [
            f"Özet: {data.get('summary', '-')}",
            f"Sektör önerisi: {data.get('sector', '-')}",
            f"Firma tipi: {data.get('company_type', '-')}",
            f"Üretim yapısı: {data.get('production_structure', '-')}",
            f"Ürün uyumu sinyalleri: {data.get('product_fit_signals', '-')}",
            "",
            "Hedef roller:",
        ]
        roles = data.get("target_roles")
        if isinstance(roles, list) and roles:
            for r in roles:
                lines.append(f"  • {r}")
        else:
            lines.append("  • —")
        lines += [
            "",
            f"Satış yaklaşımı: {data.get('sales_approach', '-')}",
            "",
            "Riskler:",
        ]
        risks = data.get("risks")
        if isinstance(risks, list) and risks:
            for r in risks:
                lines.append(f"  • {r}")
        else:
            lines.append("  • —")
        lines += ["", f"Not önerisi: {data.get('notes_suggestion', '-')}"]
        return "\n".join(lines)

    def _on_ai_research_clicked(self) -> None:
        if not self._is_new:
            return
        answer = QMessageBox.question(
            self,
            "AI analizi",
            "AI analizi çalıştırılacak. Devam edilsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._ai_suggest_result = run_ai_suggest_for_dialog(self._dialog_ai_context())
        except OpenAINotActiveError as exc:
            QMessageBox.warning(self, "AI analizi", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "AI analizi", f"İşlem başarısız:\n{exc}")
            return
        if self._ai_preview is not None:
            self._ai_preview.setPlainText(self._format_dialog_ai_preview(self._ai_suggest_result))
        if self._ai_apply_btn is not None:
            self._ai_apply_btn.setEnabled(True)

    def _on_apply_ai_to_form(self) -> None:
        if not self._ai_suggest_result:
            return
        d = self._ai_suggest_result
        filled: list[str] = []

        def take_str(key: str) -> str:
            v = d.get(key)
            if v is None:
                return ""
            return str(v).strip()

        if not self.sector_input.text().strip():
            v = take_str("sector")
            if v:
                self.sector_input.setText(v)
                filled.append("Sektör")
        if not self.company_type_input.text().strip():
            v = take_str("company_type")
            if v:
                self.company_type_input.setText(v)
                filled.append("Firma tipi")
        if not self.production_input.text().strip():
            v = take_str("production_structure")
            if v:
                self.production_input.setText(v)
                filled.append("Üretim yapısı")
        if not self.signals_input.toPlainText().strip():
            v = take_str("product_fit_signals")
            if v:
                self.signals_input.setPlainText(v)
                filled.append("Ürün uyumu sinyalleri")
        if not self.notes_input.toPlainText().strip():
            v = take_str("notes_suggestion")
            if v:
                self.notes_input.setPlainText(v)
                filled.append("Notlar")

        if filled:
            QMessageBox.information(
                self,
                "Forma Uygula",
                "Doldurulan alanlar:\n• " + "\n• ".join(filled),
            )
        else:
            QMessageBox.information(
                self,
                "Forma Uygula",
                "Uygun boş alan yoktu; mevcut alanlara dokunulmadı.",
            )


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
        self._ai_preview_by_target_id: dict[int, dict[str, Any]] = {}
        self._panel_ai_worker: _PanelAiAnalysisWorker | None = None

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

        detail_title = QLabel("Satış kararı")
        detail_title.setObjectName("SectionTitle")

        self._detail_stack = QStackedWidget()
        self._detail_empty = QWidget()
        _de_l = QVBoxLayout(self._detail_empty)
        _de_l.setContentsMargins(0, 0, 0, 0)
        self._detail_empty_label = QLabel("Tablodan bir hedef seçin.")
        self._detail_empty_label.setWordWrap(True)
        self._detail_empty_label.setObjectName("DialogSubtitle")
        _de_l.addWidget(self._detail_empty_label)
        _de_l.addStretch(1)

        self._detail_tabs = QTabWidget()
        # —— Özet ——
        oz_scroll = QScrollArea()
        oz_scroll.setWidgetResizable(True)
        oz_scroll.setFrameShape(QFrame.Shape.NoFrame)
        oz_inner = QWidget()
        oz_l = QVBoxLayout(oz_inner)
        oz_l.setSpacing(10)
        self._ozet_kayit_lbl = QLabel()
        self._ozet_kayit_lbl.setWordWrap(True)
        self._ozet_kayit_lbl.setObjectName("DialogSubtitle")
        self._ozet_kayit_lbl.setTextFormat(Qt.TextFormat.RichText)
        row_meta = QHBoxLayout()
        self._ozet_decision_lbl = QLabel()
        self._ozet_decision_lbl.setWordWrap(True)
        self._ozet_decision_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._ozet_priority_lbl = QLabel()
        self._ozet_priority_lbl.setWordWrap(True)
        self._ozet_priority_lbl.setTextFormat(Qt.TextFormat.RichText)
        self._ozet_fit_ai_lbl = QLabel()
        self._ozet_fit_ai_lbl.setWordWrap(True)
        self._ozet_diff_lbl = QLabel()
        self._ozet_diff_lbl.setWordWrap(True)
        row_meta.addWidget(self._ozet_decision_lbl, 1)
        row_meta.addWidget(self._ozet_priority_lbl, 0)
        oz_l.addWidget(self._ozet_kayit_lbl)
        oz_l.addLayout(row_meta)
        oz_l.addWidget(self._ozet_fit_ai_lbl)
        oz_l.addWidget(self._ozet_diff_lbl)

        gb_oneri = QGroupBox("Öneri")
        ol = QVBoxLayout(gb_oneri)
        self._ozet_oneri_lbl = QLabel()
        self._ozet_oneri_lbl.setWordWrap(True)
        ol.addWidget(self._ozet_oneri_lbl)
        gb_neden = QGroupBox("Neden (etki)")
        nl = QVBoxLayout(gb_neden)
        self._ozet_neden_lbl = QLabel()
        self._ozet_neden_lbl.setWordWrap(True)
        nl.addWidget(self._ozet_neden_lbl)
        self._ozet_empty_hint = QLabel()
        self._ozet_empty_hint.setWordWrap(True)
        self._ozet_empty_hint.setObjectName("DialogSubtitle")
        self._ozet_empty_hint.setVisible(False)
        oz_l.addWidget(gb_oneri)
        oz_l.addWidget(gb_neden)
        oz_l.addWidget(self._ozet_empty_hint)
        gb_skor = QGroupBox("Skor özeti (kurallar)")
        skl = QVBoxLayout(gb_skor)
        self._ozet_skor_lbl = QLabel()
        self._ozet_skor_lbl.setWordWrap(True)
        skl.addWidget(self._ozet_skor_lbl)
        oz_l.addWidget(gb_skor)
        oz_l.addStretch(1)
        oz_scroll.setWidget(oz_inner)
        self._detail_tabs.addTab(oz_scroll, "Özet")

        # —— Teknik ——
        tech_w = QWidget()
        t_l = QVBoxLayout(tech_w)
        t_l.setSpacing(8)
        self._tech_usage = QGroupBox("Teknik kullanım")
        self._tech_usage_body = QLabel()
        self._tech_usage_body.setWordWrap(True)
        _t1 = QVBoxLayout(self._tech_usage)
        _t1.addWidget(self._tech_usage_body)
        self._tech_seal = QGroupBox("Sızdırmazlık ihtiyacı")
        self._tech_seal_body = QLabel()
        self._tech_seal_body.setWordWrap(True)
        _t2 = QVBoxLayout(self._tech_seal)
        _t2.addWidget(self._tech_seal_body)
        self._tech_where = QGroupBox("Uygulama noktası")
        self._tech_where_body = QLabel()
        self._tech_where_body.setWordWrap(True)
        _t3 = QVBoxLayout(self._tech_where)
        _t3.addWidget(self._tech_where_body)
        t_l.addWidget(self._tech_usage)
        t_l.addWidget(self._tech_seal)
        t_l.addWidget(self._tech_where)
        t_l.addStretch(1)
        self._detail_tabs.addTab(tech_w, "Teknik Analiz")

        # —— Satış fırsatı ——
        sf_scroll = QScrollArea()
        sf_scroll.setWidgetResizable(True)
        sf_scroll.setFrameShape(QFrame.Shape.NoFrame)
        sf_inner = QWidget()
        sf_l = QVBoxLayout(sf_inner)
        self._sales_txt = QTextEdit()
        self._sales_txt.setReadOnly(True)
        self._sales_txt.setFrameShape(QFrame.Shape.NoFrame)
        self._sales_txt.setMinimumHeight(200)
        self._sales_txt.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sf_l.addWidget(self._sales_txt)
        sf_scroll.setWidget(sf_inner)
        self._detail_tabs.addTab(sf_scroll, "Satış Fırsatı")

        # —— Aksiyon ——
        ak_w = QWidget()
        ak_l = QVBoxLayout(ak_w)
        self._aksiyon_txt = QTextEdit()
        self._aksiyon_txt.setReadOnly(True)
        self._aksiyon_txt.setFrameShape(QFrame.Shape.NoFrame)
        self._aksiyon_txt.setMinimumHeight(200)
        ak_l.addWidget(self._aksiyon_txt)
        self._detail_tabs.addTab(ak_w, "Aksiyon")

        self._detail_stack.addWidget(self._detail_empty)
        self._detail_stack.addWidget(self._detail_tabs)

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

        ai_btn_row = QHBoxLayout()
        ai_btn_row.setContentsMargins(0, 0, 0, 0)
        ai_btn_row.setSpacing(8)
        self.ai_analyze_btn = QPushButton("AI Analiz Et")
        set_button_role(self.ai_analyze_btn, "secondary")
        self.ai_analyze_btn.setEnabled(False)
        self.ai_analyze_btn.clicked.connect(self._run_ai_analysis)
        self.ai_save_analysis_btn = QPushButton("AI Analizini Kaydet")
        set_button_role(self.ai_save_analysis_btn, "secondary")
        self.ai_save_analysis_btn.setEnabled(False)
        self.ai_save_analysis_btn.clicked.connect(self._save_ai_analysis)
        ai_btn_row.addWidget(self.ai_analyze_btn)
        ai_btn_row.addWidget(self.ai_save_analysis_btn)
        ai_btn_row.addStretch(1)

        rl.addWidget(detail_title)
        rl.addWidget(self._detail_stack, 1)
        rl.addLayout(btn_row)
        rl.addLayout(ai_btn_row)

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
            self._detail_stack.setCurrentIndex(0)
            self.save_score_btn.setEnabled(False)
            self.detail_breakdown_btn.setEnabled(False)
            self.ai_analyze_btn.setEnabled(False)
            self.ai_save_analysis_btn.setEnabled(False)
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
        self._detail_stack.setCurrentIndex(0)
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
        self._sync_ai_buttons()

    def _sync_ai_buttons(self) -> None:
        row = self._current_row_index()
        ok = row is not None and 0 <= row < len(self._rows)
        self.ai_analyze_btn.setEnabled(ok)
        if not ok:
            self.ai_save_analysis_btn.setEnabled(False)
            return
        tid = self._rows[row].id
        self.ai_save_analysis_btn.setEnabled(tid in self._ai_preview_by_target_id)

    def _lines_from_ai_suggest_dialog_shape(self, data: dict[str, Any]) -> list[str]:
        """Yeni Hedef dialogundan kaydedilen AI JSON (mock) ile uyumlu ozet."""
        lines = [
            f"Özet: {data.get('summary', '-')}",
            f"Sektör önerisi: {data.get('sector', '-')}",
            f"Firma tipi: {data.get('company_type', '-')}",
            f"Üretim yapısı: {data.get('production_structure', '-')}",
            f"Ürün uyumu sinyalleri: {data.get('product_fit_signals', '-')}",
            f"Uygunluk notu: {data.get('suitability_comment', '-')}",
            "",
            "Hedef roller:",
        ]
        roles = data.get("target_roles")
        if isinstance(roles, list) and roles:
            for r in roles:
                lines.append(f"  • {r}")
        else:
            lines.append("  • —")
        lines += ["", f"Satış yaklaşımı: {data.get('sales_approach', '-')}", "", "Riskler:"]
        risks = data.get("risks")
        if isinstance(risks, list) and risks:
            for r in risks:
                lines.append(f"  • {r}")
        else:
            lines.append("  • —")
        ns = (data.get("notes_suggestion") or "").strip()
        disc = (data.get("disclaimer") or "").strip()
        if ns or disc:
            lines.append("")
            if ns:
                lines.append(f"Not önerisi: {ns}")
            if disc:
                lines.append(f"Uyarı: {disc}")
        return lines

    def _lines_from_ai_unified_panel_shape(self, data: dict[str, Any]) -> list[str]:
        """Panel birleşik şema (FAZ 3C-B / 3D endüstriyel alanlar)."""
        lines = [
            f"Özet: {data.get('summary', '-')}",
            f"Sektör: {data.get('sector', '-')}",
            f"Firma tipi: {data.get('company_type', '-')}",
            f"Üretim yapısı: {data.get('production_structure', '-')}",
            f"Ürün uyumu sinyalleri: {data.get('product_fit_signals', '-')}",
            "",
            "TEKNİK / KULLANIM",
            f"Gerçek kullanım alanı (makine/proses): {data.get('technical_usage', '-')}",
            f"Sızdırmazlık ihtiyacı: {data.get('sealing_need', '-')}",
            f"Uygulama noktası (hangi bölüm/hat): {data.get('sealing_where', '-')}",
            "",
            "SÜRLAS ÜRÜN EŞLEMESİ",
        ]
        sfp = data.get("surlas_fit_products")
        if isinstance(sfp, list) and sfp:
            for p in sfp:
                lines.append(f"  • {p}")
        else:
            lines.append("  • —")
        lines += [
            "",
            f"Satış zorluğu: {data.get('sales_difficulty', '-')}",
            f"Uygunluk (AI tahmini %): {data.get('fit_score_percent', '-')}",
            f"Karar: {data.get('decision', '-')}",
            "",
            "Genel ürün / fonksiyon listesi (model):",
        ]
        for p in data.get("products") or []:
            lines.append(f"  • {p}")
        if not (data.get("products") or []):
            lines.append("  • —")
        lines += ["", "Departmanlar / fonksiyonlar:"]
        for d in data.get("departments") or []:
            lines.append(f"  • {d}")
        if not (data.get("departments") or []):
            lines.append("  • —")
        lines += [
            "",
            f"Satış stratejisi: {data.get('sales_strategy', '-')}",
            "",
            "Riskler:",
        ]
        for r in data.get("risks") or []:
            lines.append(f"  • {r}")
        if not (data.get("risks") or []):
            lines.append("  • —")
        lines += [
            "",
            f"İlk mesaj önerisi: {data.get('first_message', '-')}",
            "",
            f"Not önerisi: {data.get('notes_suggestion', '-')}",
        ]
        return lines

    def _lines_from_ai_display_dict(self, data: dict[str, Any], *, is_preview: bool) -> list[str]:
        lines: list[str] = []
        if is_preview:
            lines.append("Durum: Önizleme (kayıtlı değil)")
            lines.append("")
        if "sales_approach" in data and "target_roles" in data:
            return lines + self._lines_from_ai_suggest_dialog_shape(data)
        if (
            "sales_strategy" in data
            and "notes_suggestion" in data
            and "target_roles" not in data
            and "suitability" not in data
        ):
            return lines + self._lines_from_ai_unified_panel_shape(data)
        lines.append(f"Özet: {data.get('summary', '-')}")
        lines.append(f"Uygunluk: {data.get('suitability', '-')}")
        lines.append("")
        lines.append("Ürünler:")
        for p in data.get("products") or []:
            lines.append(f"  • {p}")
        if not (data.get("products") or []):
            lines.append("  • —")
        lines.append("")
        lines.append("Departmanlar:")
        for d in data.get("departments") or []:
            lines.append(f"  • {d}")
        if not (data.get("departments") or []):
            lines.append("  • —")
        lines.append("")
        lines.append(f"Satış stratejisi: {data.get('sales_strategy', '-')}")
        lines.append("")
        lines.append("Riskler:")
        for r in data.get("risks") or []:
            lines.append(f"  • {r}")
        if not (data.get("risks") or []):
            lines.append("  • —")
        cn = (data.get("confidence_notes") or "").strip()
        disc = (data.get("disclaimer") or "").strip()
        if cn or disc:
            lines.append("")
            if cn:
                lines.append(f"Güven notu: {cn}")
            if disc:
                lines.append(f"Uyarı: {disc}")
        return lines

    def _build_ai_assessment_section(self, t: ResearchTarget) -> list[str]:
        tid = t.id
        preview = self._ai_preview_by_target_id.get(tid)
        if preview:
            return self._lines_from_ai_display_dict(preview, is_preview=True)
        raw = (getattr(t, "ai_analysis_json", None) or "").strip()
        if raw:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                return ["Kayıtlı AI verisi okunamadı."]
            if not isinstance(data, dict):
                return ["Kayıtlı AI verisi geçersiz."]
            meta: list[str] = []
            ts = getattr(t, "ai_analysis_updated_at", None)
            model = getattr(t, "ai_model", None) or "-"
            ver = getattr(t, "ai_analysis_version", None) or data.get("schema_version") or "-"
            ts_txt = ts.strftime("%d.%m.%Y %H:%M") if ts else "-"
            meta.append(f"Sürüm: {ver}  ·  Model: {model}  ·  Zaman: {ts_txt}")
            meta.append("")
            return meta + self._lines_from_ai_display_dict(data, is_preview=False)
        return ["Henüz AI analizi yok. «AI Analiz Et» ile başlatın."]

    def _run_ai_analysis(self) -> None:
        row = self._current_row_index()
        if row is None or row < 0 or row >= len(self._rows):
            return
        t = self._rows[row]
        msg = "AI analizi çalıştırılacak. Devam edilsin mi?"
        if load_ai_settings().provider == "openai":
            msg += (
                "\n\nBu işlem harici OpenAI servisine veri gönderebilir "
                "ve ücret oluşturabilir."
            )
        answer = QMessageBox.question(
            self,
            "AI analizi",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if self._panel_ai_worker is not None and self._panel_ai_worker.isRunning():
            QMessageBox.information(
                self,
                "AI analizi",
                "Önceki analiz tamamlanana kadar bekleyin.",
            )
            return
        self._panel_ai_worker = _PanelAiAnalysisWorker(t.id, self)
        self._panel_ai_worker.finished_ok.connect(self._on_panel_ai_worker_ok)
        self._panel_ai_worker.finished_err.connect(self._on_panel_ai_worker_err)
        self._panel_ai_worker.finished.connect(self._on_panel_ai_thread_finished)
        self.ai_analyze_btn.setEnabled(False)
        self._panel_ai_worker.start()

    def _on_panel_ai_worker_ok(self, tid: int, result: dict[str, Any]) -> None:
        self._ai_preview_by_target_id[tid] = result
        ridx = self._current_row_index()
        if ridx is not None and 0 <= ridx < len(self._rows) and self._rows[ridx].id == tid:
            self._populate_detail(ridx)
        self._sync_ai_buttons()

    def _on_panel_ai_worker_err(self, tid: int, message: str) -> None:
        _ = tid
        QMessageBox.warning(self, "AI analizi", message)
        self._sync_ai_buttons()

    def _on_panel_ai_thread_finished(self) -> None:
        if self._panel_ai_worker is not None:
            self._panel_ai_worker.deleteLater()
            self._panel_ai_worker = None
        self._sync_ai_buttons()

    def _save_ai_analysis(self) -> None:
        row = self._current_row_index()
        if row is None or row < 0 or row >= len(self._rows):
            return
        t = self._rows[row]
        tid = t.id
        preview = self._ai_preview_by_target_id.get(tid)
        if not preview:
            return
        session = get_session()
        try:
            s = load_ai_settings()
            model_name = effective_openai_model(s) if s.provider == "openai" else "mock"
            update_research_target_ai_analysis(session, tid, preview, model_name=model_name)
        except Exception as exc:
            QMessageBox.critical(self, "AI Analizi", f"Kaydedilemedi:\n{exc}")
            return
        finally:
            session.close()
        del self._ai_preview_by_target_id[tid]
        self.refresh_table(preserve_target_id=tid)

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
        payload = {**dialog.get_data(), **dialog.get_ai_persistence_fields()}
        create_research_target(payload)
        self.refresh_table()

    def _current_row_index(self) -> int | None:
        indexes = self.table.selectionModel().selectedRows()
        if not indexes:
            return None
        return indexes[0].row()

    def _on_selection_changed(self) -> None:
        row = self._current_row_index()
        if row is None or row < 0 or row >= len(self._rows):
            self._detail_stack.setCurrentIndex(0)
            self._sync_save_score_button()
            self._sync_detail_breakdown_button()
            self._sync_ai_buttons()
            return
        self._populate_detail(row)
        self._sync_save_score_button()

    def _get_display_ai_dict(self, t: ResearchTarget) -> dict[str, Any]:
        tid = t.id
        prev = self._ai_preview_by_target_id.get(tid)
        if isinstance(prev, dict):
            return dict(prev)
        raw = (getattr(t, "ai_analysis_json", None) or "").strip()
        if not raw:
            return {}
        try:
            d = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return d if isinstance(d, dict) else {}

    def _ozet_sparse_record(self, t: ResearchTarget) -> bool:
        return not (t.website or "").strip() or len((t.product_fit_signals or "").strip()) < 8

    def _fill_teknik_tab(self, data: dict[str, Any]) -> None:
        def blk(key: str) -> str:
            v = (data.get(key) or "").strip()
            return _fmt_truncate(v, 320) if v else "—"

        self._tech_usage_body.setText(blk("technical_usage"))
        self._tech_seal_body.setText(blk("sealing_need"))
        self._tech_where_body.setText(blk("sealing_where"))

    def _fill_sales_firsat_tab(self, t: ResearchTarget, data: dict[str, Any]) -> None:
        blocks: list[str] = []
        summ = (data.get("summary") or "").strip()
        if summ:
            blocks.append("Neden satılabilir\n• " + _fmt_truncate(summ, 280))

        prods = data.get("surlas_fit_products") if isinstance(data.get("surlas_fit_products"), list) else []
        if not prods:
            prods = data.get("products") if isinstance(data.get("products"), list) else []
        if prods:
            blocks.append(
                "Hangi ürünler\n" + "\n".join(f"• {p}" for p in [str(x) for x in prods][:14])
            )

        deps = data.get("departments") if isinstance(data.get("departments"), list) else []
        if deps:
            blocks.append("Hangi departman\n" + "\n".join(f"• {d}" for d in [str(x) for x in deps][:10]))

        risks = data.get("risks") if isinstance(data.get("risks"), list) else []
        if risks:
            blocks.append("Riskler\n" + "\n".join(f"• {r}" for r in [str(x) for x in risks][:10]))

        if not blocks:
            blocks.append(
                "Kayıt ve AI çıktısı geldikçe bu sekme dolar.\n\n"
                "Şimdi: Web ve ürün sinyali ekleyin → «AI Analiz Et» veya «Skoru Kaydet»."
            )
        self._sales_txt.setPlainText("\n\n".join(blocks))

    def _fill_aksiyon_tab(self, t: ResearchTarget, data: dict[str, Any]) -> None:
        if data and (
            data.get("sales_strategy")
            or data.get("sales_approach")
            or data.get("first_message")
            or data.get("departments")
            or data.get("target_roles")
        ):
            steps = _build_aksiyon_steps(data)
        else:
            steps = [
                "Sektör + ürün sinyali (min. 12 karakter) girerek kaydı güçlendir",
                "«AI Analiz Et» ile karar ve aksiyon önerilerini üret (ortam/koşullar için uyarıya bakın)",
                "3 gün içinde «Skoru Kaydet» ile önceliği kalıcılaştır; «Detayı gör» ile kural analizini incele",
            ]
        self._aksiyon_txt.setPlainText("\n".join(f"{i + 1}. {s}" for i, s in enumerate(steps)))

    def _populate_detail(self, row: int) -> None:
        if row < 0 or row >= len(self._rows):
            self._detail_stack.setCurrentIndex(0)
            self.detail_breakdown_btn.setEnabled(False)
            self._current_breakdown_for_dialog = None
            self.ai_analyze_btn.setEnabled(False)
            self.ai_save_analysis_btn.setEnabled(False)
            return
        t = self._rows[row]
        self._detail_stack.setCurrentIndex(1)
        self._detail_tabs.setCurrentIndex(0)

        data = self._get_display_ai_dict(t)
        ks = int(t.fit_score or 0)
        band = self._panel_score_band_label(ks)
        sk = (t.status or "new").strip().lower()
        status_tr = self._status_label_tr(sk)

        loc = f"{t.city or '-'}, {t.country or '-'}"
        lines_html = [
            f"<b>{t.name}</b>",
            f"{loc} · Web: {t.website or '—'} · Durum: {status_tr}",
        ]
        sig = (t.product_fit_signals or "").strip()
        if sig:
            lines_html.append(f"Ürün sinyali: {_fmt_truncate(sig, 100)}")
        notes = (t.notes or "").strip()
        if notes:
            lines_html.append(f"Not: {_fmt_truncate(notes, 100)}")
        self._ozet_kayit_lbl.setText("<br/>".join(lines_html))

        dec_raw = (data.get("decision") or "").strip()
        self._ozet_decision_lbl.setText(f"<b>Karar</b> {dec_raw or '—'}")
        self._ozet_priority_lbl.setText(f"Öncelik: <b>{band}</b><br/>Skor: {ks}")

        fp = data.get("fit_score_percent")
        if fp is not None and str(fp).strip() != "":
            self._ozet_fit_ai_lbl.setText(f"AI uygunluk (tahmini %): {fp}")
            self._ozet_fit_ai_lbl.setVisible(True)
        else:
            self._ozet_fit_ai_lbl.clear()
            self._ozet_fit_ai_lbl.setVisible(False)

        sd_short = (data.get("sales_difficulty") or "").strip()
        self._ozet_diff_lbl.setText(
            f"Satış zorluğu: {_fmt_truncate(sd_short, 200)}" if sd_short else "Satış zorluğu: —"
        )

        oneri = _build_oneri_line(data) if data else ""
        if not oneri:
            role = "Satınalma/teknik sorumlu"
            if (t.sector or "").strip():
                oneri = _fmt_truncate(
                    f"— → {role} hedefle → {t.sector} için teknik netleştirme soruları hazırla", 120
                )
            else:
                oneri = "— → Web ve ürün sinyali ekle → ardından AI analizi ve skor"

        self._ozet_oneri_lbl.setText(oneri)

        neden = _build_neden_line(data) if data else ""
        if not neden:
            comment, _sugg = self._build_fit_comment(t)
            neden = _fmt_truncate(comment, 120) if comment else ""

        self._ozet_neden_lbl.setText(neden or "—")

        sparse = self._ozet_sparse_record(t) or not data
        self._ozet_empty_hint.setVisible(bool(sparse))
        if sparse:
            self._ozet_empty_hint.setText(
                "Veri eksik:\n"
                "→ Web ekle\n"
                "→ Ürün sinyali gir\n"
                "→ AI analizi çalıştır"
            )
        else:
            self._ozet_empty_hint.clear()

        sk_lines = self._build_skor_analizi_section(t)
        self._ozet_skor_lbl.setText("\n".join(sk_lines[:10]))

        self._fill_teknik_tab(data)
        self._fill_sales_firsat_tab(t, data)
        self._fill_aksiyon_tab(t, data)

        self._sync_detail_breakdown_button()
        self._sync_ai_buttons()

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
