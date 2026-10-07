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
- À faire : 2 Musique, 3 Synthesia, 4 OBS, 5 Rendu, 6 QC, 7 Publication, 8 Analytics, 9 `piano auto`.
- Les phases 3-4 et `doctor` complet exigent un Mac réel (Synthesia, OBS, permissions Accessibility/Screen Recording) : impossible à valider dans le conteneur cloud.
