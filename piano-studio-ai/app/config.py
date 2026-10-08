from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_settings(path: Path | None = None) -> dict:
    with open(path or ROOT / "config" / "settings.yaml") as f:
        s = yaml.safe_load(f)
    local = ROOT / "data" / "local_settings.json"           # réglages faits dans la page (ex. dossier MIDI), prioritaires sur settings.yaml
    if path is None and local.exists():
        try:
            import json
            for k, v in json.loads(local.read_text()).items():
                s[k] = {**s.get(k, {}), **v} if isinstance(v, dict) and isinstance(s.get(k), dict) else v
        except Exception:
            pass
    return s


def save_local(key: str, value: dict) -> None:
    import json
    f = ROOT / "data" / "local_settings.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    cur = json.loads(f.read_text()) if f.exists() else {}
    cur[key] = {**cur.get(key, {}), **value}
    f.write_text(json.dumps(cur, ensure_ascii=False, indent=1))


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
