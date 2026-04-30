from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parent
    spec_file = project_root / "CRM.spec"
    icon_file = project_root / "assets" / "app.ico"
    print(f"Python yorumlayicisi: {sys.executable}")
    print(f"Spec dosyasi: {spec_file}")

    if shutil.which("pyinstaller") is None:
        try:
            __import__("PyInstaller")
        except ModuleNotFoundError:
            print("PyInstaller kurulu degil. Once `pip install -r requirements.txt` calistirin.")
            return 1

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        str(spec_file),
    ]
    if icon_file.exists():
        print(f"Ikon bulundu ve spec tarafindan baglanacak: {icon_file}")
    else:
        print(f"Ikon bulunamadi, varsayilan ikon kullanilacak: {icon_file}")
    print("Calistiriliyor:", " ".join(command))
    return subprocess.call(command, cwd=project_root)


if __name__ == "__main__":
    raise SystemExit(main())
