# Piano Studio AI

Tu es l'ingénieur principal du projet. Objectif : un studio automatisé de tutoriels piano (Synthesia → OBS → FFmpeg → publication), local sur Mac, avec un minimum d'intervention humaine.

## Règles
- Légalité d'abord : seul un morceau `LEGAL_CONFIRMED` entre dans le pipeline (`database.db.song_usable`). Doute = `SKIP SONG`. Jamais de MIDI piraté, ni de contournement de DRM/paywall.
- Déterministe > LLM ; API > navigateur ; Accessibility > coordonnées souris ; SQLite > fichiers dispersés ; configuration > code en dur ; retry > crash ; validation > publication.
- Secrets dans `.env`/trousseau uniquement, jamais dans le code ni les logs.
- Ne crée pas de fausse fonctionnalité : une commande non implémentée le dit (code retour 2).
- Petites modifications, testées (`python -m pytest`), sans casser l'existant.
- Une plateforme en échec ne bloque jamais les autres.

## État (phases du cahier des charges)
- Phase 1 Fondations : fait (structure, config, SQLite, logs, CLI `doctor/status/queue/init`, tests).
- Phase 2 (partielle) : parseur/analyse MIDI, sélection de passage, import avec garde-fou licence (`piano import`, `piano analyze`). Pas encore de découverte de tendances ni de téléchargement.
- Phase 5 (partielle) : rendu FFmpeg 9:16 depuis templates (`app/renderer/render.py`). Pas encore de logo/texte/variantes plateformes.
- À faire : 3 Synthesia, 4 OBS, 6 QC, 7 Publication, 8 Analytics, 9 `piano auto` + scheduler launchd + dashboard.
- Les phases 3-4 et `doctor` complet exigent un Mac réel (Synthesia, OBS, permissions Accessibility/Screen Recording) : impossible à valider dans le conteneur cloud.

## Mode autonome (cloud)
- Pas besoin de Synthesia/OBS : `app/visualizer` rend les notes qui tombent + audio synthétisé, en headless. `piano run` = 1 vidéo de bout en bout (morceau légal → analyse → rendu → QC → contenu → publication).
- Sources : compositions originales générées + mélodies du domaine public transcrites (`music_discovery/generator.py`).
- Planification : `.github/workflows/piano-studio.yml` (2/jour). YouTube nécessite les secrets OAuth ; TikTok/Instagram/Facebook exigent une app approuvée par la plateforme (adaptateurs `NOT_CONFIGURED`). L'outbox garde toujours la vidéo prête.

## Mode Mac (Synthesia de l'utilisateur)
- `engine: auto` : si `piano mac-check` est tout vert (Synthesia, Accessibility, capture écran, `synthesia.calibrated: true`), la vidéo est capturée depuis l'app Synthesia (`synthesia_controller/mac.py`, `renderer/compose.py`) ; sinon repli automatique sur le rendu intégré.
- Section : le MIDI est découpé sur le passage choisi (`trim_midi`), Synthesia le joue en entier. Audio = piano synthétisé aligné via `lead_in_seconds`/`capture_trim` (à étalonner sur le Mac : NON testé sur un vrai Mac).
- Planification : `piano mac-install` écrit l'agent launchd (2/jour).
