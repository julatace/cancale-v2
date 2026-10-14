#!/bin/bash
# Glisse un fichier MIDI sur ce fichier (ou colle son chemin) -> une vidéo « billes » apparaît sur le Bureau.
cd "$(dirname "$0")"
f="$1"
if [ -z "$f" ]; then read -r -p "Chemin du fichier MIDI (glisse-le ici puis Entrée) : " f; fi
f="${f%\"}"; f="${f#\"}"; f="${f//\\ / }"
./p.sh generer-billes "$f"
read -r -p "Terminé. Appuie sur Entrée pour fermer." _
