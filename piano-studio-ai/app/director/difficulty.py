"""Niveaux de difficulté = tempo cible. Plus c'est rapide, plus c'est dur."""
from dataclasses import replace

DEFAULTS = {
    "mode": "rotate",                       # rotate = alterne les niveaux ; sinon nom d'un niveau fixe (ex. "moyen")
    "rotation": ["facile", "moyen", "difficile"],
    "levels": {                              # bpm cible, densité max (notes/s) acceptée pour ce niveau
        "debutant":  {"bpm": 60,  "max_density": 2.5, "max_rate": 2.0, "label": "Débutant"},
        "facile":    {"bpm": 80,  "max_density": 4.0, "max_rate": 3.0, "label": "Facile"},
        "moyen":     {"bpm": 100, "max_density": 6.0, "max_rate": 4.5, "label": "Moyen"},
        "difficile": {"bpm": 130, "max_density": 9.0, "max_rate": 6.5, "label": "Difficile"},
        "expert":    {"bpm": 160, "max_density": 14.0, "max_rate": 9.0, "label": "Expert"},
    },
}


def config(s: dict) -> dict:
    d = {**DEFAULTS, **s.get("difficulty", {})}
    mine = s.get("difficulty", {}).get("levels", {})
    d["levels"] = {k: {**v, **mine.get(k, {})} for k, v in DEFAULTS["levels"].items()}          # réglages du fichier complétés par les valeurs par défaut
    d["levels"].update({k: v for k, v in mine.items() if k not in d["levels"]})
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


def onset_rate(notes, window: float = 2.0, group: float = 0.04) -> float:
    """Vitesse « de lecture » : nombre d'attaques par seconde (un accord = une attaque) sur les passages les plus rapides
    (90e centile des fenêtres de `window` secondes). C'est ce que l'œil doit suivre pour que les notes ne « fuient » pas."""
    ons = sorted(n.start for n in notes)
    if not ons:
        return 0.0
    merged = [ons[0]]
    for x in ons[1:]:
        if x - merged[-1] > group:
            merged.append(x)
    end = merged[-1]
    if end <= window:
        return len(merged) / max(window, end or 1)
    import bisect
    rates, t0 = [], 0.0
    while t0 + window <= end + 1e-9:
        rates.append((bisect.bisect_left(merged, t0 + window) - bisect.bisect_left(merged, t0)) / window)
        t0 += window / 2
    rates.sort()
    return rates[min(int(len(rates) * 0.9), len(rates) - 1)]


def comfortable_extra(notes, max_rate: float | None, floor: float = 0.5) -> float:
    """Facteur (<= 1) à appliquer en plus pour que le passage le plus rapide ne dépasse pas `max_rate` attaques/s."""
    if not max_rate:
        return 1.0
    r = onset_rate(notes)
    return 1.0 if r <= max_rate else max(max_rate / r, floor)
