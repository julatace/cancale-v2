from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_settings(path: Path | None = None) -> dict:
    with open(path or ROOT / "config" / "settings.yaml") as f:
        return yaml.safe_load(f)


def resolve(settings: dict, key: str) -> Path:
    p = Path(settings["paths"][key])
    return p if p.is_absolute() else ROOT / p


def load_env(path: Path | None = None) -> None:
    """Charge le fichier .env (clés des plateformes) dans l'environnement, sans écraser ce qui est déjà défini."""
    import os
    f = path or ROOT / ".env"
    if not f.exists():
        return
    for line in f.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip().strip('"').strip("'")
        if v and k.strip() not in os.environ:
            os.environ[k.strip()] = v
