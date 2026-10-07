# Piano Studio AI

```bash
cd piano-studio-ai
pip install -e '.[dev]'
piano doctor     # diagnostic de l'environnement
piano init       # crée la base SQLite
piano status
python -m pytest
```
Config : `config/settings.yaml`, `config/platforms.yaml`, `templates/*.json`. Secrets : copier `.env.example` en `.env`.
`piano auto`, `start`, `dry-run`… ne sont pas encore implémentés (voir `CLAUDE.md`).

## Interface
```bash
./p.sh ui      # ouvre http://127.0.0.1:8765 : niveau (facile/moyen/difficile) + format (vertical court / horizontal long)
```

`piano ui` crée d'office les deux formats (vertical court + horizontal long) avec le même morceau, et garde `stock.target` morceaux d'avance téléchargés en arrière-plan (réserve visible en haut de la page).

## Publication automatique sur YouTube (une seule fois)
1. https://console.cloud.google.com : créer un projet, activer **YouTube Data API v3**.
2. « Écran de consentement OAuth » : type *Externe*, vous ajouter comme *utilisateur test*.
3. « Identifiants » > créer un **ID client OAuth** de type *Application de bureau*. Copier l'ID et le secret dans `.env`
   (`YOUTUBE_CLIENT_ID=...`, `YOUTUBE_CLIENT_SECRET=...`).
4. `./p.sh youtube-login` : autoriser dans la page Google ; le jeton est écrit dans `.env` tout seul.
5. Cocher « Publier ensuite » dans la page. Attention : tant que le projet Google n'a pas passé l'audit de YouTube, les vidéos envoyées
   par l'API restent **privées** ; il suffit de les passer en publiques dans YouTube Studio (ou de demander l'audit).

## TikTok (publication par l'API officielle)
TikTok n'autorise la publication par programme qu'aux applications qu'il a approuvées. Étapes :
1. https://developers.tiktok.com : créer une application, ajouter les produits **Login Kit** et **Content Posting API**.
2. Dans l'application, ajouter l'adresse de redirection `http://127.0.0.1:8085/` et vous ajouter comme utilisateur de test (mode Sandbox).
3. Copier la clé et le secret dans `.env` (`TIKTOK_CLIENT_KEY=...`, `TIKTOK_CLIENT_SECRET=...`), puis `./p.sh tiktok-login`.
4. Mode `draft` (par défaut) : la vidéo arrive dans la boîte de réception de l'app TikTok, vous touchez « Publier » (le texte est à coller depuis la page).
   Mode `direct` (réglage `tiktok.mode`) : publication immédiate, **privée** tant que TikTok n'a pas approuvé l'application.
