#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/scripts/audit_entries.py"

"$ROOT_DIR/.venv/bin/python" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "Vishnusahasranamam" \
  --osx-bundle-identifier "local.vishnusahasranamam.app" \
  --add-data "$ROOT_DIR/data/ocr/pages.jsonl:data/ocr" \
  --add-data "$ROOT_DIR/data/index/index.json:data/index" \
  --add-data "$ROOT_DIR/data/index/slokas.json:data/index" \
  --add-data "$ROOT_DIR/data/index/nama_numbers.json:data/index" \
  --hidden-import PySide6.QtCore \
  --hidden-import PySide6.QtGui \
  --hidden-import PySide6.QtWidgets \
  --hidden-import shiboken6 \
  --exclude-module tkinter \
  --exclude-module matplotlib \
  --exclude-module pandas \
  --exclude-module scipy \
  --exclude-module numpy \
  --distpath "$ROOT_DIR/dist" \
  --workpath "$ROOT_DIR/build/pyinstaller" \
  --specpath "$ROOT_DIR/build" \
  "$ROOT_DIR/src/vishnu_desktop_app.py"
