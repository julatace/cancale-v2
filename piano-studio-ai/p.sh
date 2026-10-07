#!/bin/bash
# Raccourci : ~/cancale-v2/piano-studio-ai/p.sh <commande>   (ex. p.sh ui, p.sh mac-setup, p.sh run --force-synthesia)
cd "$(dirname "$0")" || exit 1
source .venv/bin/activate || { echo "❌ Environnement Python introuvable : relancez scripts/install_mac.sh"; exit 1; }
git pull -q || echo "⚠ Mise à jour impossible (version actuelle utilisée) : $(git status -s | head -3)"
if [ "$1" = "ui" ]; then
  # un ancien « piano ui » encore ouvert garderait l'ancienne version : on l'arrête
  for pid in $(lsof -ti tcp:8765 2>/dev/null); do
    if ps -p "$pid" -o command= | grep -q "piano"; then kill "$pid" && echo "↻ Ancienne page arrêtée (processus $pid)."; sleep 1; fi
  done
  echo "→ Version du programme : $(git rev-parse --short HEAD)"
  echo "→ Si la page ne s'ouvre pas toute seule, ouvrez http://127.0.0.1:8765 dans Safari."
fi
piano "$@"
