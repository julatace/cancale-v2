# Dossier de passation : tout ce qu'il faut savoir pour reprendre l'agent

Dépôt : `julatace/cancale-v2`, dossier `piano-studio-ai/`, branche `claude/peaceful-dirac-rh4evw`. Utilisateur : francophone, Mac, Chrome.
Tout se lance depuis `piano-studio-ai/` avec `./p.sh <commande>` (met à jour par `git pull`, active le venv, garde le Mac éveillé pour `ui`).

## 1. Ce que veut l'utilisateur (règles NON négociables)
1. Agent 100 % autonome : à partir de fichiers MIDI (`~/Desktop/MIDI`) il fabrique des vidéos de tutoriel piano, écrit titre / description / hashtags, publie.
2. Chaque vidéo est envoyée à TikTok puis à YouTube **dès son montage**, **programmée DANS TikTok / YouTube** à la date de l'agenda (elle sort même Mac éteint).
   **Jamais** de programmation dans l'app, **jamais** de publication en masse, **toujours public**, brouillon seulement en secours.
3. Agenda : l'utilisateur choisit un nombre de vidéos par jour pour les prochains jours (max 10 jours, limite TikTok). Tout est fabriqué le jour même, une vidéo à la fois.
4. Aucun doublon, jamais. Un envoi incertain n'est jamais renvoyé tout seul.
5. Seule la DERNIÈRE fabrication peut être envoyée (`data/last_batch.json`). Les anciennes vidéos ne sont jamais renvoyées.
6. Une vidéo sur les plateformes est **supprimée du Mac** (fichier, miniature, copie de secours). Disque économe.
7. Compte : profil Chrome « angeled92 » (dossier `Profile 26`) pour TikTok ET YouTube. Un seul onglet réutilisé par site (pas de nouvel onglet à chaque envoi).
8. YouTube : 4 envois par jour maximum (le surplus attend `WAITING` puis reprend). Une vidéo verticale = Short ; l'horizontale = vidéo normale.
9. Pas de mention de licence (« public domain ») dans les textes. Musique de l'utilisateur uniquement (`songs.only_mine: true`).
10. L'utilisateur veut du **simple, fiable, beau**. Interface en 3 sections (Accueil / Mes morceaux / Réglages). Style de vidéo : dessiné à la main, caméra calme.

## 2. Architecture (où est quoi)
- `app/cli.py` : commandes (`ui`, `run`, `autostart`, `instance-init`, `chrome-profiles`, `clean`, `youtube-web`, `tiktok-web`…).
- `app/ui/server.py` + `page.py` : page locale `http://127.0.0.1:8765` (stdlib, aucun framework). `Job` = une fabrication à la fois, journal en direct, barre d'évolution (`app/director/progress.py`).
- `app/director/pipeline.py` : choix du morceau → analyse → passage/refrain → niveau/tempo → rendu → QC → miniature. `run_one()`.
- `app/visualizer/sketch.py` : rendu « dessiné » (Pillow → ffmpeg), caméra fixe/lente, supersample 2, CRF 16, loudnorm -14 LUFS, contrôle de synchro. `synth.py` : piano macOS (`afconvert`) ou piano numpy de secours + `align_audio` (recalage son/notes).
- `app/publisher/` : `tiktok_web.py`, `youtube_web.py` pilotent Chrome par AppleScript (`execute javascript`) ; `__init__.py` choisit les adaptateurs.
- `app/scheduler/queue.py` : `publish_video` (idempotent par plateforme, verrou `SEND_LOCK` + verrou entre processus `data/.send.lock`), agenda (`slots_for_days`), limite YouTube, reprise.
- `app/scheduler/autopilot.py` : pilote automatique (fabrique ce qui manque dans l'agenda, pause progressive après échec). `app/notify.py` : notifications macOS.
- `app/director/cleanup.py` : suppression après publication, purge des restes. `app/clips/` : agent « clips » (voir `AGENT_CLIPS.md`).
- Base SQLite `data/piano.sqlite3` : songs, videos, publications (UNIQUE video_id+platform), schedule (traces `DONE` = programmé dans les réseaux), errors.
- Réglages : `config/settings.yaml` + `data/local_settings.json` (la page l'écrit). Autre agent : variable `PIANO_INSTANCE=nom` → tout est séparé dans `data/instances/<nom>/`.

## 3. Publication : ce qui a été appris (à ne pas redécouvrir)
- Chrome : activer « Autoriser JavaScript dans Apple Events » (menu Présentation → Développeur) DANS le profil utilisé. Safari a été abandonné (réglage introuvable).
- Ouverture : `open -na "Google Chrome" --args --profile-directory="Profile 26"`, puis un onglet repéré par id (`tab id T of window id W`) et réutilisé (`TABS`).
- Fichier : injecté directement dans l'`input[type=file]` en base64 par morceaux (240 000 car.) ; la boîte de dialogue macOS n'est qu'un secours (jamais de frappe dans la barre de recherche de Chrome : vérifier d'abord la fenêtre).
- Titre/description : saisie vérifiée par relecture, jusqu'à 5 essais (YouTube écrasait le titre).
- YouTube : envoi lent → le bouton Publier reste désactivé : attendre la fin du traitement. Visibilité `tp-yt-paper-radio-button[name="PUBLIC"]` (vérifié). Programmation : `#second-container-expand-button`, `#datepicker-trigger`, `#time-of-day-container input`, date/heure au format local (`toLocaleDateString/TimeString`), Entrée via System Events.
- TikTok : studio « Planifier » + sélecteurs de date/heure : **NON vérifié sur la vraie page** (champs introuvables en test). Pour corriger : `data/debug/tiktok_planifier_page.txt` (liste des contrôles vus) et captures `data/debug/steps/`. Brouillon en secours.
- Statuts « bons » : PUBLISHED / DRAFT / SCHEDULED. Échecs AMBIGUS (après le dernier clic) → `UNCERTAIN`, jamais renvoyés seuls.
- Ne jamais toucher à la souris/clavier pendant un envoi (cliclick et System Events utilisés en dernier recours).

## 4. Qualité vidéo / son
- Caméra fixe quand tout le morceau tient (jusqu'à 52 touches blanches), sinon glissement lent plafonné. Notes visibles 3,6 s à l'avance. Barre qui touche le clavier exactement au début de la note.
- Son : piano système (GM) + pédale auto + légère réverbération, normalisé -14 LUFS, pic < -1,5 dB. Synchro mesurée (`onset_lag`) et recalée automatiquement ; contrôle final sur le fichier encodé (`sync_ms`).
- Niveaux = tempo (Facile 80 / Moyen 100 / Difficile 130 BPM). Retour utilisateur à traiter : il se plaint que la musique « se ruine » (tempo trop lent ? passage coupé ? son ?) : demander quel point gêne avant de changer.

## 5. Ce qui reste incertain (à vérifier en conditions réelles)
- Programmation TikTok native (voir §3). Programmation YouTube après envoi lent (corrigée, pas revérifiée).
- Piano `afconvert` sur le Mac : non écouté. Latence éventuelle visible dans le journal (« Son recalé de … ms »).
- Le Mac doit rester allumé et connecté à sa session pendant la fabrication/l'envoi ; ensuite les réseaux publient seuls.

## 6. Comment travailler
- Tests : `python -m pytest -q` (≈ 250 tests, ~7 min). Ne pas pousser avec un test rouge. Vérifier `git rev-parse` local == `git ls-remote origin <branche>`.
- Petites modifications testées, pas de fausse fonctionnalité, secrets uniquement dans `.env`.
- Répondre en français, simple, sans jargon, et donner les commandes Terminal exactes (`cd ~/cancale-v2/piano-studio-ai`, `git pull`, `./p.sh ui`).
- Adresse de la page : http://127.0.0.1:8765 (autre agent : voir son port à la création).
