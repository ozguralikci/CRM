from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "CRM"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def get_app_root() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def get_user_data_dir() -> Path:
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        base = Path(local_app_data)
    else:
        base = Path.home() / "AppData" / "Local"

    target = base / APP_NAME
    target.mkdir(parents=True, exist_ok=True)
    return target


def get_database_path() -> Path:
    if is_frozen():
        return get_user_data_dir() / "crm.sqlite"
    return get_app_root() / "crm.sqlite"


def get_logs_dir() -> Path:
    target = get_user_data_dir() / "logs"
    target.mkdir(parents=True, exist_ok=True)
    return target


def get_log_file_path() -> Path:
    return get_error_log_file_path()


def get_app_log_file_path() -> Path:
    return get_logs_dir() / "crm-app.log"


def get_error_log_file_path() -> Path:
    return get_logs_dir() / "crm-error.log"


def get_asset_path(filename: str) -> Path:
    asset_path = get_app_root() / "assets" / filename
    if asset_path.exists():
        return asset_path
    return get_app_root() / filename


def get_exchange_dir() -> Path:
    documents = Path.home() / "Documents"
    target = documents / APP_NAME / "Aktarimlar"
    target.mkdir(parents=True, exist_ok=True)
    return target


def get_default_export_path(filename: str) -> str:
    return str(get_exchange_dir() / filename)


def get_default_import_dir() -> str:
    return str(get_exchange_dir())
