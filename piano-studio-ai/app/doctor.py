import platform
import shutil
import sys
from pathlib import Path

OK, WARN, FAIL = "✅", "⚠️", "❌"


def run_checks(settings: dict, root: Path) -> list[tuple[str, str, str]]:
    is_mac = platform.system() == "Darwin"
    paths = settings["paths"]
    res = []
    sketch = settings.get("style", "sketch") == "sketch"
    res.append(("Mac", OK if (is_mac or sketch) else WARN, "" if is_mac else f"OS={platform.system()} (macOS requis pour Synthesia/OBS)"))
    py_ok = sys.version_info >= (3, 10)
    res.append(("Python", OK if py_ok else FAIL, platform.python_version()))
    ff = shutil.which("ffmpeg")
    res.append(("FFmpeg", OK if ff else FAIL, ff or "brew install ffmpeg"))
    for name, key in (("OBS", "obs_app"), ("Synthesia", "synthesia_app")):
        found = Path(paths[key]).exists()
        res.append((name, OK if (found or sketch) else WARN, paths[key] if found else ("non requis (style dessiné)" if sketch else f"introuvable: {paths[key]}")))
    # Permissions macOS: vérifiables seulement sur Mac, via l'utilisateur
    for name in ("Accessibility", "Screen Recording"):
        res.append((name, OK if sketch else WARN, "non requis (style dessiné)" if sketch else "à vérifier manuellement (Réglages Système > Confidentialité)" if is_mac else "n/a hors macOS"))
    if is_mac:
        res.append(("Piano (son)", OK if shutil.which("afconvert") else WARN, "" if shutil.which("afconvert") else "afconvert absent : piano de secours"))
    free_gb = shutil.disk_usage(root).free / 1e9
    res.append(("Storage", OK if free_gb >= 3 else FAIL, f"{free_gb:.0f} Go libres"))
    return res


def internet_ok() -> bool:
    import socket
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=3).close()
        return True
    except OSError:
        return False


def render(results, net: bool) -> tuple[str, bool]:
    results = results + [("Internet", OK if net else FAIL, "")]
    lines = ["PIANO STUDIO AI", "─" * 24, ""]
    for n, s, d in results:
        lines.append(f"{n:<18}{s}  {d}".rstrip())
    ready = all(s == OK for _, s, _ in results)
    lines += ["", "System status: " + ("READY" if ready else "ACTION REQUIRED")]
    return "\n".join(lines), ready
