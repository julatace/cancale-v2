"""Niveaux de difficulté = tempo cible. Plus c'est rapide, plus c'est dur."""
from dataclasses import replace

DEFAULTS = {
    "mode": "rotate",                       # rotate = alterne les niveaux ; sinon nom d'un niveau fixe (ex. "moyen")
    "rotation": ["facile", "moyen", "difficile"],
    "levels": {                              # bpm cible, densité max (notes/s) acceptée pour ce niveau
        "debutant":  {"bpm": 60,  "max_density": 2.5, "label": "Débutant"},
        "facile":    {"bpm": 80,  "max_density": 4.0, "label": "Facile"},
        "moyen":     {"bpm": 100, "max_density": 6.0, "label": "Moyen"},
        "difficile": {"bpm": 130, "max_density": 9.0, "label": "Difficile"},
        "expert":    {"bpm": 160, "max_density": 14.0, "label": "Expert"},
    },
}


def config(s: dict) -> dict:
    d = {**DEFAULTS, **s.get("difficulty", {})}
    d["levels"] = {**DEFAULTS["levels"], **s.get("difficulty", {}).get("levels", {})}
    return d


def choose_level(s: dict, videos_done: int, override: str | None = None) -> tuple[str, dict]:
    d = config(s)
    if override:
        name = override
    else:
        name = d["rotation"][videos_done % len(d["rotation"])] if d["mode"] == "rotate" else d["mode"]
    if name not in d["levels"]:
        raise ValueError(f"niveau inconnu : {name}")
    return name, d["levels"][name]


def stretch_notes(notes, factor: float):
    """factor > 1 : plus rapide (durées raccourcies) ; < 1 : plus lent."""
    return [replace(n, start=n.start / factor, end=n.end / factor) for n in notes]


def speed_factor(piece_bpm: float, target_bpm: float, lo=0.4, hi=2.5) -> float:
    return max(lo, min(hi, target_bpm / piece_bpm))
