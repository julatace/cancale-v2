#!/bin/bash
# Installation Piano Studio AI sur Mac. Usage: bash scripts/install_mac.sh
set -e
cd "$(dirname "$0")/.."
[ -x /opt/homebrew/bin/brew ] && eval "$(/opt/homebrew/bin/brew shellenv)"
if ! command -v brew >/dev/null; then
  echo "❌ Homebrew absent. Installez-le depuis https://brew.sh puis relancez ce script."; exit 1
fi
command -v ffmpeg >/dev/null || brew install ffmpeg
command -v cliclick >/dev/null || brew install cliclick
# Le Python d'Apple (3.9) est trop vieux : on utilise Python 3.12 de Homebrew.
brew list python@3.12 >/dev/null 2>&1 || brew install python@3.12
PY="$(brew --prefix python@3.12)/bin/python3.12"
rm -rf .venv
"$PY" -m venv .venv
. .venv/bin/activate
pip install -q --upgrade pip
pip install -q -e .
[ -f .env ] || cp .env.example .env
echo "✅ Installé. Lancement du diagnostic :"
piano mac-check || true
echo
echo "Ensuite : piano run   (génère une vidéo test)   puis   piano mac-install   (planification 2/jour)"
