"""Notifications macOS (centre de notifications) : l'agent te prévient quand quelque chose demande ton attention. Sans effet hors Mac."""
import platform
import subprocess
import time

_SENT: dict[str, float] = {}
REPEAT_AFTER = 6 * 3600


def send(title: str, message: str, key: str | None = None, run=subprocess.run, now=time.time) -> bool:
    """Une même alerte (même clé) n'est pas répétée avant 6 h. Retourne True si une notification a été envoyée."""
    k = key or f"{title}|{message}"
    if now() - _SENT.get(k, float("-inf")) < REPEAT_AFTER:
        return False
    if platform.system() != "Darwin":
        return False
    esc = lambda t: str(t).replace("\\", "\\\\").replace('"', '\\"')[:200]
    try:
        run(["osascript", "-e", f'display notification "{esc(message)}" with title "{esc(title)}" sound name "Glass"'],
            capture_output=True, timeout=10)
    except Exception:
        return False
    _SENT[k] = now()
    return True
