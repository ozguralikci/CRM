from __future__ import annotations

import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QStatusBar,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from crm_app.ui.actions_page import ActionsPage
from crm_app.ui.companies_page import CompaniesPage
from crm_app.ui.contacts_page import ContactsPage
from crm_app.ui.dashboard_page import DashboardPage
from crm_app.ui.field_management_page import FieldManagementPage
from crm_app.ui.opportunities_page import OpportunitiesPage
from crm_app.ui.offers_page import OffersPage
from crm_app.ui.samples_page import SamplesPage
from crm_app.ui.styles import build_stylesheet
from crm_app.ui.login_dialog import LoginDialog
from crm_app.ui.change_password_dialog import ChangePasswordDialog
from crm_app.services.auth_service import get_user_by_id
from crm_app.utils.app_paths import get_asset_path
from crm_app.utils.logging_utils import log_exception


LOGGER = logging.getLogger(__name__)



class MainWindow(QMainWindow):
    menu_icon_map = {
        "Dashboard": QStyle.StandardPixmap.SP_ComputerIcon,
        "Sirketler": QStyle.StandardPixmap.SP_DirIcon,
        "Kisiler": QStyle.StandardPixmap.SP_FileDialogDetailedView,
        "Aksiyonlar": QStyle.StandardPixmap.SP_BrowserReload,
        "Fırsatlar": QStyle.StandardPixmap.SP_FileDialogListView,
        "Teklifler": QStyle.StandardPixmap.SP_DialogSaveButton,
        "Numuneler": QStyle.StandardPixmap.SP_FileDialogContentsView,
        "Alan Yonetimi": QStyle.StandardPixmap.SP_FileDialogInfoView,
    }
    menu_items = [
        "Dashboard",
        "Sirketler",
        "Kisiler",
        "Aksiyonlar",
        "Fırsatlar",
        "Teklifler",
        "Numuneler",
        "Alan Yonetimi",
    ]

    def __init__(self, *, active_db_path: str = "") -> None:
        super().__init__()
        self.setWindowTitle("CRM - Satis Yonetimi")
        self.resize(1440, 860)
        icon_path = get_asset_path("app.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        status_bar = QStatusBar()
        status_bar.setObjectName("MainStatusBar")
        self.setStatusBar(status_bar)
        if active_db_path:
            active_db_label = QLabel(f"Aktif DB: {active_db_path}")
            active_db_label.setObjectName("ActiveDbLabel")
            status_bar.addPermanentWidget(active_db_label, 1)

        central = QWidget()
        central.setObjectName("MainShell")
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        sidebar_container = QWidget()
        sidebar_container.setObjectName("SidebarPanel")
        sidebar_container.setFixedWidth(228)
        sidebar_layout = QVBoxLayout(sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(12)

        brand_card = QFrame()
        brand_card.setObjectName("BrandCard")
        brand_layout = QHBoxLayout(brand_card)
        brand_layout.setContentsMargins(6, 4, 6, 10)
        brand_layout.setSpacing(10)

        brand_mark = QLabel()
        brand_mark.setObjectName("BrandMark")
        brand_mark.setFixedSize(10, 10)

        brand_title = QLabel("CRM")
        brand_title.setObjectName("BrandTitle")
        brand_subtitle = QLabel("satis operasyon merkezi")
        brand_subtitle.setObjectName("BrandSubtitle")
        brand_subtitle.setWordWrap(True)

        brand_text_layout = QVBoxLayout()
        brand_text_layout.setContentsMargins(0, 0, 0, 0)
        brand_text_layout.setSpacing(0)
        brand_text_layout.addWidget(brand_title)
        brand_text_layout.addWidget(brand_subtitle)

        brand_layout.addWidget(brand_mark, 0, Qt.AlignmentFlag.AlignTop)
        brand_layout.addLayout(brand_text_layout)
        brand_layout.addStretch()

        self.sidebar = QListWidget()
        self.sidebar.setObjectName("SidebarMenu")
        for item in self.menu_items:
            menu_item = QListWidgetItem(item, self.sidebar)
            menu_item.setIcon(self.style().standardIcon(self.menu_icon_map[item]))
        self.sidebar.currentRowChanged.connect(self.change_page)
        self.sidebar.setSpacing(1)

        sidebar_layout.addWidget(brand_card)
        sidebar_layout.addWidget(self.sidebar, 1)

        self.pages = QStackedWidget()
        self.pages.setObjectName("PageViewport")
        self.dashboard_page = DashboardPage()
        self.companies_page = CompaniesPage()
        self.contacts_page = ContactsPage()
        self.actions_page = ActionsPage()
        self.opportunities_page = OpportunitiesPage()
        self.offers_page = OffersPage()
        self.samples_page = SamplesPage()
        self.field_management_page = FieldManagementPage()

        self.pages.addWidget(self.dashboard_page)
        self.pages.addWidget(self.companies_page)
        self.pages.addWidget(self.contacts_page)
        self.pages.addWidget(self.actions_page)
        self.pages.addWidget(self.opportunities_page)
        self.pages.addWidget(self.offers_page)
        self.pages.addWidget(self.samples_page)
        self.pages.addWidget(self.field_management_page)
        self.page_refresh_callbacks = {
            0: ("dashboard", self.dashboard_page.refresh),
            1: ("companies", self.companies_page.refresh_table),
            2: ("contacts", self.contacts_page.refresh_table),
            3: ("actions", self.actions_page.refresh_table),
            4: ("opportunities", self.opportunities_page.refresh_table),
            5: ("offers", self.offers_page.refresh_table),
            6: ("samples", self.samples_page.refresh_table),
            7: ("field_management", self.field_management_page.refresh_table),
        }

        page_frame = QFrame()
        page_frame.setObjectName("PageFrame")
        page_layout = QVBoxLayout(page_frame)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.addWidget(self.pages)

        layout.addWidget(sidebar_container)
        layout.addWidget(page_frame, 1)

        self.sidebar.setCurrentRow(0)

    def change_page(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        page_entry = self.page_refresh_callbacks.get(index)
        if not page_entry:
            return
        page_name, refresh_callback = page_entry
        try:
            refresh_callback()
        except Exception as exc:
            log_exception(LOGGER, "page_refresh", exc, page=page_name, index=index)
            raise

def run(*, active_db_path: str = "") -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyleSheet(build_stylesheet())
    app.setFont(QFont("Segoe UI", 10))
    app.setApplicationDisplayName("CRM")
    icon_path = get_asset_path("app.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    login = LoginDialog()
    if not login.exec():
        return 0

    if login.authenticated_user_id is None:
        return 0

    user = get_user_by_id(login.authenticated_user_id)
    if not user:
        return 0

    if getattr(user, "must_change_password", False):
        change_dialog = ChangePasswordDialog(user_id=user.id)
        if not change_dialog.exec():
            return 0

    window = MainWindow(active_db_path=active_db_path)
    window.show()

    return app.exec()
