"""Arrêt demandé par l'utilisateur (bouton « Arrêter ») : vérifié à chaque étape longue (enregistrement, rendu)."""
import threading

CANCEL = threading.Event()          # « Annuler » : tout jeter
STOP_RECORD = threading.Event()     # « Arrêter l'enregistrement » : couper la capture et garder ce qui est enregistré


class Cancelled(Exception):
    pass


def check():
    if CANCEL.is_set():
        raise Cancelled("création arrêtée par l'utilisateur")
