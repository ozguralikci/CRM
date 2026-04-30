from __future__ import annotations

import sys
import logging

from PySide6.QtWidgets import QApplication, QMessageBox

from crm_app.database.session import init_database
from crm_app.ui.main_window import run
from crm_app.utils.app_paths import get_database_path, get_error_log_file_path
from crm_app.utils.logging_utils import append_fatal_report, configure_logging, log_exception


LOGGER = logging.getLogger(__name__)


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
    LOGGER.info("Application starting | database_path=%s", get_database_path())
    try:
        init_database()
        LOGGER.info("Database initialization completed")
        raise SystemExit(run())
    except SystemExit:
        raise
    except Exception as exc:
        log_exception(LOGGER, "application_startup", exc, error_log=get_error_log_file_path())
        _show_fatal_error(exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
