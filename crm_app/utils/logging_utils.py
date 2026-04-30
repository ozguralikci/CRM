from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import sys
import traceback
from pathlib import Path
from typing import Any

from crm_app.utils.app_paths import get_app_log_file_path, get_error_log_file_path


LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
MAX_LOG_BYTES = 1_048_576
BACKUP_COUNT = 5

_LOGGING_CONFIGURED = False


def configure_logging() -> tuple[Path, Path]:
    global _LOGGING_CONFIGURED
    app_log = get_app_log_file_path()
    error_log = get_error_log_file_path()
    if _LOGGING_CONFIGURED:
        return app_log, error_log

    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    app_handler = RotatingFileHandler(
        app_log,
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(formatter)

    error_handler = RotatingFileHandler(
        error_log,
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    root_logger.addHandler(app_handler)
    root_logger.addHandler(error_handler)

    if not getattr(sys, "frozen", False):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    logging.captureWarnings(True)
    _LOGGING_CONFIGURED = True
    logging.getLogger(__name__).info(
        "Logging configured | app_log=%s | error_log=%s",
        app_log,
        error_log,
    )
    return app_log, error_log


def log_exception(logger: logging.Logger, action: str, exc: BaseException, **context: Any) -> None:
    context_text = " | ".join(f"{key}={value}" for key, value in context.items() if value not in (None, ""))
    message = (
        f"{action} failed | type={type(exc).__name__} | message={exc}"
        + (f" | {context_text}" if context_text else "")
    )
    logger.exception(message)


def append_fatal_report(exc: BaseException, *, action: str = "fatal_error", **context: Any) -> Path:
    error_log = get_error_log_file_path()
    context_text = "\n".join(
        f"{key}: {value}" for key, value in context.items() if value not in (None, "")
    )
    traceback_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    payload = [
        "=" * 80,
        f"action: {action}",
        f"exception_type: {type(exc).__name__}",
        f"exception_message: {exc}",
    ]
    if context_text:
        payload.append(context_text)
    payload.extend(["traceback:", traceback_text.rstrip(), ""])
    try:
        with error_log.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(payload))
    except OSError:
        pass
    return error_log
