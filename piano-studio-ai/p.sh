#!/bin/bash
# Raccourci : ~/cancale-v2/piano-studio-ai/p.sh <commande>   (ex. p.sh ui, p.sh mac-setup, p.sh run --force-synthesia)
cd "$(dirname "$0")" || exit 1
source .venv/bin/activate || { echo "❌ Environnement Python introuvable : relancez scripts/install_mac.sh"; exit 1; }
git pull -q || echo "⚠ Mise à jour impossible (version actuelle utilisée) : $(git status -s | head -3)"
if [ "$1" = "ui" ]; then echo "→ Si la page ne s'ouvre pas toute seule, ouvrez http://127.0.0.1:8765 dans Safari ou Chrome."; fi
piano "$@"
