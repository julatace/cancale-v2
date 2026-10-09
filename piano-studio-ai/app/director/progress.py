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
