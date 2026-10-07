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
