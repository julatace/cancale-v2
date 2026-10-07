#!/bin/bash
# Installation Piano Studio AI sur Mac. Usage: bash scripts/install_mac.sh
set -e
cd "$(dirname "$0")/.."
if ! command -v brew >/dev/null; then
  echo "❌ Homebrew absent. Installez-le depuis https://brew.sh puis relancez ce script."; exit 1
fi
command -v ffmpeg >/dev/null || brew install ffmpeg
command -v python3 >/dev/null || brew install python
python3 -m venv .venv
. .venv/bin/activate
pip install -q -e .
[ -f .env ] || cp .env.example .env
echo "✅ Installé. Lancement du diagnostic :"
piano mac-check || true
echo
echo "Ensuite : piano run   (génère une vidéo test)   puis   piano mac-install   (planification 2/jour)"
