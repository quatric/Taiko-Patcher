#!/bin/zsh
# Build the standalone GUI (PyInstaller). Output: tools/dist/Taiko-Patcher(.app)
set -eu
cd "${0:a:h}"
command -v pyinstaller >/dev/null || { echo "pyinstaller not found (pip install pyinstaller tkinterdnd2)"; exit 1; }
pyinstaller --noconfirm Taiko-Patcher.spec
echo "built: tools/dist/Taiko-Patcher"
