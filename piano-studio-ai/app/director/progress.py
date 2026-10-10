"""Avancement de la vidéo en cours de fabrication (0-100 %) : lu par l'interface pour la barre d'évolution."""
import threading
import time

_lock = threading.Lock()
_state = {"label": "", "pct": 0.0, "t": 0.0}


def report(label: str, pct: float):
    with _lock:
        _state.update(label=label, pct=max(0.0, min(float(pct), 100.0)), t=time.time())


def reset():
    report("", 0)


def get() -> dict:
    with _lock:
        return dict(_state)


def where(e: BaseException) -> str:
    """Endroit du code où l'erreur s'est produite (« fichier.py:ligne dans fonction ») : permet de corriger sans deviner."""
    import traceback
    tb = traceback.extract_tb(e.__traceback__)
    mine = [f for f in tb if "/app/" in f.filename.replace("\\", "/")] or tb
    if not mine:
        return ""
    f = mine[-1]
    return f"{f.filename.replace(chr(92), '/').split('/app/')[-1]}:{f.lineno} dans {f.name}"
