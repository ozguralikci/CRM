from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from openpyxl import Workbook


def export_rows(
    file_path: str,
    headers: list[str],
    rows: Iterable[Iterable[object]],
) -> None:
    target = Path(file_path)
    suffix = target.suffix.lower()

    if suffix == ".xlsx":
        _export_xlsx(target, headers, rows)
        return

    _export_csv(target, headers, rows)


def _export_csv(
    target: Path,
    headers: list[str],
    rows: Iterable[Iterable[object]],
) -> None:
    with target.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        for row in rows:
            writer.writerow([_stringify_cell(value) for value in row])


def _export_xlsx(
    target: Path,
    headers: list[str],
    rows: Iterable[Iterable[object]],
) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Veriler"
    sheet.append(headers)

    for row in rows:
        sheet.append([_stringify_cell(value) for value in row])

    workbook.save(target)


def _stringify_cell(value: object) -> object:
    if value is None:
        return ""
    return value
