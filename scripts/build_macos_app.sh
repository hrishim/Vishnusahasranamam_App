#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/scripts/audit_all_namas.py"
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/scripts/audit_canonical_tables.py"
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/scripts/audit_app_name_search.py"
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/scripts/audit_app_exact_search.py"
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/scripts/build_derivation_overrides.py"
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/scripts/audit_rendered_entries_quality.py"
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/scripts/audit_rendered_text_defects.py"
"$ROOT_DIR/.venv/bin/python" "$ROOT_DIR/scripts/audit_rendered_formatting.py"
"$ROOT_DIR/.venv/bin/python" -m pytest \
  "$ROOT_DIR/tests/test_canonical_namas.py" \
  "$ROOT_DIR/tests/test_textutil.py" \
  "$ROOT_DIR/tests/test_web_app.py" \
  -q

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
  --add-data "$ROOT_DIR/data/index/canonical_namas.json:data/index" \
  --add-data "$ROOT_DIR/data/index/derivation_overrides.json:data/index" \
  --hidden-import PySide6.QtCore \
  --hidden-import PySide6.QtGui \
  --hidden-import PySide6.QtWidgets \
  --hidden-import shiboken6 \
  --exclude-module PySide6.QtNetwork \
  --exclude-module PySide6.QtNetworkAuth \
  --exclude-module tkinter \
  --exclude-module matplotlib \
  --exclude-module pandas \
  --exclude-module scipy \
  --exclude-module numpy \
  --distpath "$ROOT_DIR/dist" \
  --workpath "$ROOT_DIR/build/pyinstaller" \
  --specpath "$ROOT_DIR/build" \
  "$ROOT_DIR/src/vishnu_desktop_app.py"
