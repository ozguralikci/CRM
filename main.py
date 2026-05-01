from __future__ import annotations

import sys
import logging
import os
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

import crm_app.database.session as db_session
from crm_app.database.session import configure_database, init_database
from crm_app.services.backup_service import run_startup_checks_and_backup
from crm_app.ui.main_window import run
from crm_app.utils.app_paths import get_database_path, get_error_log_file_path, get_user_data_dir
from crm_app.utils.logging_utils import append_fatal_report, configure_logging, log_exception


LOGGER = logging.getLogger(__name__)


def resolve_active_db_path() -> Path:
    env_db = os.getenv("CRM_DB_PATH")
    if env_db:
        return Path(env_db)

    preferred = Path("D:/CRM/crm.sqlite")
    if preferred.exists():
        return preferred

    return get_database_path()


def _last_active_db_file_path() -> Path:
    return get_user_data_dir() / "last_active_db.txt"


def _read_last_active_db_path() -> str:
    path = _last_active_db_file_path()
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _write_last_active_db_path(active_db: Path) -> None:
    path = _last_active_db_file_path()
    try:
        path.write_text(str(active_db), encoding="utf-8")
    except OSError:
        pass


def _warn_if_db_path_changed(active_db: Path) -> None:
    last_db = _read_last_active_db_path()
    if not last_db:
        return
    if last_db == str(active_db):
        return

    app = QApplication.instance() or QApplication(sys.argv)
    response = QMessageBox.warning(
        None,
        "Veritabani Yolu Degisti",
        f"Aktif veritabani onceki acilistan farkli.\n\nOnceki: {last_db}\nSimdi:  {active_db}\n\nDevam etmek istiyor musunuz?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if response != QMessageBox.StandardButton.Yes:
        raise SystemExit(0)


def _show_fatal_error(exc: BaseException) -> None:
    log_file = append_fatal_report(exc, action="fatal_error")
    log_exception(LOGGER, "fatal_error", exc, error_log=log_file)

    app = QApplication.instance() or QApplication(sys.argv)
    QMessageBox.critical(
        None,
        "CRM Baslatma Hatasi",
        f"Uygulama baslatilirken beklenmeyen bir hata olustu.\n\nDetaylar: {exc}\n\nGunluk: {log_file}",
    )


def _handle_unexpected_exception(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_traceback: object,
) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    error = exc_value
    if getattr(error, "__traceback__", None) is None:
        error.__traceback__ = exc_traceback  # type: ignore[attr-defined]
    _show_fatal_error(error)


def main() -> None:
    configure_logging()
    sys.excepthook = _handle_unexpected_exception
    active_db = resolve_active_db_path()
    LOGGER.info("ACTIVE DATABASE: %s", active_db)
    try:
        if not active_db.exists():
            raise FileNotFoundError(f"Active database not found: {active_db}")

        _warn_if_db_path_changed(active_db)
        configure_database(active_db)
        LOGGER.info("ORM DATABASE: %s", db_session.DATABASE_PATH)
        run_startup_checks_and_backup(
            db_path=active_db,
            backups_dir=Path("D:/CRM/backups"),
            retention=30,
        )
        init_database()
        LOGGER.info("Database initialization completed")
        _write_last_active_db_path(active_db)
        raise SystemExit(run(active_db_path=str(active_db)))
    except SystemExit:
        raise
    except Exception as exc:
        log_exception(LOGGER, "application_startup", exc, error_log=get_error_log_file_path())
        _show_fatal_error(exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
