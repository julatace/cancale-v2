#!/bin/bash
# Raccourci : ~/cancale-v2/piano-studio-ai/p.sh <commande>   (ex. p.sh mac-setup, p.sh run --force-synthesia)
cd "$(dirname "$0")" && source .venv/bin/activate && git pull -q && piano "$@"
