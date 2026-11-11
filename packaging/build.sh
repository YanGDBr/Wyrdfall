#!/usr/bin/env sh
# Builds dist/wyrdfall (Linux/macOS). Run from the repository root.
set -e
python -m pip install --upgrade pyinstaller
python -m pip install -e .
pyinstaller --noconfirm --clean packaging/wyrdfall.spec
echo "Pronto: dist/wyrdfall"
