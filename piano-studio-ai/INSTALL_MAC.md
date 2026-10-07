# Installation sur Mac (une seule fois, ~15 min)

1. **Télécharger le projet** : Terminal →
   `git clone -b claude/peaceful-dirac-rh4evw https://github.com/julatace/cancale-v2.git && cd cancale-v2/piano-studio-ai`
2. **Installer** : `bash scripts/install_mac.sh` (installe ffmpeg + Python si besoin, puis lance le diagnostic).
3. **Autoriser le Terminal** : Réglages Système → Confidentialité et sécurité →
   *Accessibilité* ✔ Terminal, et *Enregistrement de l'écran* ✔ Terminal. Fermez et rouvrez le Terminal.
4. **Diagnostic** : `source .venv/bin/activate && piano mac-check` → tout doit être ✅ (sauf « Étalonnage fait »).
5. **Vidéo test** : `piano run`. Synthesia s'ouvre seul et joue. Regardez la vidéo dans `data/published/`.
   Son décalé ? Changez `lead_in_seconds` / `capture_trim` dans `config/settings.yaml`, relancez.
6. Vidéo OK → mettez `calibrated: true` dans `config/settings.yaml`.
7. **Automatiser** : `piano mac-install`, puis la commande `launchctl load …` affichée.
   Pour réveiller le Mac : `sudo pmset repeat wakeorpoweron MTWRFSU 08:55:00`.
