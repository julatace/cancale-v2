#!/bin/bash
# Double-clic : met à jour et lance l'agent piano, puis ouvre sa page.
cd "$(dirname "$0")" 2>/dev/null || cd ~/cancale-v2/piano-studio-ai || { echo "❌ Dossier introuvable : ~/cancale-v2/piano-studio-ai"; read -n 1 -s -r -p "Appuie sur une touche pour fermer"; exit 1; }
./p.sh ui
echo; read -n 1 -s -r -p "L'agent s'est arrêté. Appuie sur une touche pour fermer."
