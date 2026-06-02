#!/bin/zsh
cd "$(dirname "$0")"
.venv/bin/vishnu-web --host 0.0.0.0 --port 8765 --open
