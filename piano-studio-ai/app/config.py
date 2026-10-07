from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_settings(path: Path | None = None) -> dict:
    with open(path or ROOT / "config" / "settings.yaml") as f:
        return yaml.safe_load(f)


def resolve(settings: dict, key: str) -> Path:
    p = Path(settings["paths"][key])
    return p if p.is_absolute() else ROOT / p
