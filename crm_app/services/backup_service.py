from __future__ import annotations

import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path


_BACKUP_NAME_RE = re.compile(r"^crm_(\d{8})_(\d{6})\.sqlite$")


def run_startup_checks_and_backup(db_path: Path, backups_dir: Path, retention: int = 30) -> None:
    """
    Startup safety layer:
    - If DB file does not exist: do nothing (no side effects).
    - Run SQLite integrity_check using read-only connection.
    - Create a timestamped backup copy.
    - Enforce retention policy (keep newest N).
    """
    if not db_path.exists():
        return

    ok, details = run_integrity_check(db_path)
    if not ok:
        raise RuntimeError(f"SQLite integrity_check failed: {details}")

    create_backup(db_path, backups_dir)
    enforce_retention(backups_dir, retention=retention)


def run_integrity_check(db_path: Path) -> tuple[bool, str]:
    db_uri = f"file:{db_path}?mode=ro"
    try:
        with sqlite3.connect(db_uri, uri=True) as conn:
            rows = conn.execute("PRAGMA integrity_check").fetchall()
    except sqlite3.Error as exc:
        return False, f"sqlite_error={exc}"

    results = [str(row[0]) for row in rows if row and row[0] is not None]
    if len(results) == 1 and results[0].strip().lower() == "ok":
        return True, "ok"

    details = "; ".join(r.strip() for r in results if r.strip()) or "unknown"
    return False, details


def create_backup(db_path: Path, backups_dir: Path) -> Path:
    backups_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backups_dir / f"crm_{timestamp}.sqlite"

    if backup_path.exists():
        # Never overwrite an existing backup.
        raise FileExistsError(f"Backup already exists: {backup_path}")

    shutil.copy2(db_path, backup_path)
    return backup_path


def enforce_retention(backups_dir: Path, retention: int = 30) -> None:
    if retention <= 0:
        return
    if not backups_dir.exists():
        return

    backups: list[Path] = []
    for path in backups_dir.iterdir():
        if not path.is_file():
            continue
        if _BACKUP_NAME_RE.match(path.name):
            backups.append(path)

    # Name sort works because the timestamp is lexicographically sortable.
    backups.sort(key=lambda p: p.name, reverse=True)
    to_delete = backups[retention:]

    for path in to_delete:
        path.unlink()
