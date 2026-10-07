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
