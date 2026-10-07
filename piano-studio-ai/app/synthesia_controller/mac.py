"""Pilotage de l'app Synthesia achetée par l'utilisateur (macOS) : ouverture du MIDI, lecture, capture d'écran.
Aucune API Synthesia n'existe : AppleScript/System Events + ffmpeg avfoundation. Étalonné par `piano mac-check`."""
import platform
import shutil
import re
import subprocess
import time
from pathlib import Path


def sh(cmd, timeout=60):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def osa(script: str, run=sh):
    return run(["osascript", "-e", script])


def screen_devices(run=sh) -> list[tuple[int, str]]:
    err = run(["ffmpeg", "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""]).stderr
    out, in_video = [], False
    for line in err.splitlines():
        if "video devices" in line: in_video = True
        elif "audio devices" in line: in_video = False
        m = re.search(r"\[(\d+)\] (.+)$", line)
        if in_video and m and "Capture screen" in m.group(2):
            out.append((int(m.group(1)), m.group(2)))
    return out


def check(cfg: dict, run=sh, system=platform.system) -> list[tuple[str, bool, str]]:
    """Retourne [(test, ok, détail)] — utilisé par `piano mac-check` et par le mode auto pour décider du repli."""
    res = []
    if system() != "Darwin":
        return [("macOS", False, f"système={system()}")]
    app = Path(cfg["app_path"])
    res.append(("Synthesia installé", app.exists(), str(app)))
    ok, why = accessibility_ok(run)
    res.append(("Accessibilité (cliquer dans Synthesia)", ok, why))
    dev = screen_devices(run)
    res.append(("Écran capturable (ffmpeg avfoundation)", bool(dev), ", ".join(d[1] for d in dev) or "ffmpeg absent ou aucun écran"))
    res.append(("cliclick (vrai clic souris)", bool(shutil.which("cliclick")), "brew install cliclick" if not shutil.which("cliclick") else ""))
    res.append(("Étalonnage fait", bool(cfg.get("calibrated")), "mettre synthesia.calibrated: true après vérification visuelle"))
    return res


def ready(cfg, run=sh, system=platform.system) -> bool:
    return all(ok for _, ok, _ in check(cfg, run, system))


def _ints(s: str) -> list[int]:
    return [int(float(x)) for x in re.findall(r"-?\d+(?:\.\d+)?", s)]


def accessibility_ok(run=sh) -> tuple[bool, str]:
    """Vrai test : lire la position d'une fenêtre exige l'autorisation Accessibilité du Terminal."""
    r = osa('tell application "System Events" to get UI elements enabled', run)
    if r.returncode != 0:
        return False, "osascript refusé : " + (r.stderr or "").strip()[:100]
    if "false" in r.stdout.lower():
        return False, "Accessibilité désactivée pour le Terminal (Réglages Système > Confidentialité et sécurité > Accessibilité)"
    return True, ""


def screen_points(run=sh) -> tuple[int, int]:
    b = _ints(osa('tell application "Finder" to get bounds of window of desktop', run).stdout)
    return b[2], b[3]


def window_geometry(run=sh) -> tuple[int, int, int, int]:
    """(x, y, largeur, hauteur) de la fenêtre Synthesia, en points écran."""
    r = osa('tell application "System Events" to tell process "Synthesia" to get {position, size} of window 1', run)
    v = _ints(r.stdout)
    if r.returncode or len(v) != 4:
        raise RuntimeError(f"fenêtre Synthesia introuvable: {r.stderr.strip()[:100]}")
    return tuple(v)


def click(x: int, y: int, run=sh) -> bool:
    """Vrai clic souris (cliclick) ; repli sur System Events si cliclick n'est pas installé."""
    if shutil.which("cliclick"):
        return run(["cliclick", f"m:{x},{y}", "w:250", f"c:{x},{y}"]).returncode == 0
    return osa(f'tell application "System Events" to click at {{{x}, {y}}}', run).returncode == 0


def start_playback(cfg: dict, run=sh, sleep=time.sleep) -> str:
    """Mode « Regarder et écouter seulement » -> clic sur la carte puis « Continuer ». Entrée en dernier recours."""
    osa('tell application "Synthesia" to activate', run)
    sleep(0.5)
    if cfg.get("start_mode", "click") == "click":
        x, y, w, _h = window_geometry(run)
        k = screen_points(run)[0] / 2000.0          # px de capture -> points écran
        card = (x + int(cfg["listen_card_from_left_px"] * k), y + int(cfg["listen_card_from_top_px"] * k))
        cont = (x + w - int(cfg["continue_from_right_px"] * k), y + int(cfg["continue_from_top_px"] * k))
        ok1 = click(*card, run=run)
        sleep(0.7)
        ok2 = click(*cont, run=run)
        if ok1 and ok2:
            return f"click{card}+click{cont}"
    r = osa('tell application "System Events" to key code 36', run)
    if r.returncode != 0:
        raise RuntimeError("impossible de piloter Synthesia : " + (r.stderr or "").strip()[:150])
    return "return"


def arrange_window_portrait(cfg: dict, run=sh) -> tuple[int, int, int, int]:
    """Fenêtre Synthesia en portrait (même rapport que la zone 1080x1650 du montage), collée en haut, centrée."""
    sw, sh_ = screen_points(run)
    h = sh_ - cfg.get("portrait_margin_points", 70)
    w = int(h * 1080 / 1650)
    x, y = (sw - w) // 2, 28
    osa(f'tell application "System Events" to tell process "Synthesia" to set position of window 1 to {{{x}, {y}}}', run)
    osa(f'tell application "System Events" to tell process "Synthesia" to set size of window 1 to {{{w}, {h}}}', run)
    return window_geometry(run)


def crop_fractions(cfg: dict, run=sh) -> tuple[float, float, float, float] | None:
    """Zone de la fenêtre Synthesia (sans barre de titre) en fractions de l'écran, pour recadrer la capture."""
    try:
        sw, sh_ = screen_points(run)
        x, y, w, h = window_geometry(run)
    except Exception:
        return None
    tb = cfg.get("titlebar_points", 24)
    return (max(x, 0) / sw, (max(y, 0) + tb) / sh_, min(w, sw) / sw, (h - tb) / sh_)


def debug_frames(video: Path, outdir: Path, times=(2, 8, 25), run=sh) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    out = []
    for t in times:
        f = outdir / f"{video.stem}_{t}s.jpg"
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", str(video), "-frames:v", "1", "-vf", "scale=1000:-2", str(f)])
        if f.exists(): out.append(f)
    return out


def record(midi: Path, duration: float, out: Path, cfg: dict, run=sh, sleep=time.sleep) -> tuple[Path, tuple | None]:
    """Relance Synthesia sur le MIDI, clique « Continuer », capture l'écran. Retourne (capture, zone de recadrage)."""
    ok, why = accessibility_ok(run)
    if not ok:
        raise RuntimeError(f"Accessibilité non autorisée : {why}")
    screen = screen_devices(run)[0][0]
    total = duration + cfg["lead_in_seconds"] + cfg["tail_seconds"]
    osa('tell application "Synthesia" to quit', run)   # état propre à chaque vidéo
    sleep(2)
    run(["open", "-a", str(cfg["app_path"]), str(midi)])
    sleep(cfg["load_seconds"])
    cap = subprocess.Popen(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "avfoundation", "-framerate", "30",
                            "-capture_cursor", "0", "-i", f"{screen}:none", "-t", str(total), "-c:v", "libx264",
                            "-preset", "ultrafast", "-crf", "16", "-pix_fmt", "yuv420p", str(out)], stderr=subprocess.PIPE)
    sleep(1.0)
    try:
        start_playback(cfg, run)            # la lecture démarre dans la fenêtre large (disposition connue)
        crop = None
        if cfg.get("portrait", True):
            try:
                arrange_window_portrait(cfg, run)   # gros plan : fenêtre verticale
                sleep(1.5)
            except Exception:
                pass                                # repli : fenêtre telle quelle
        crop = crop_fractions(cfg, run)
        cap.wait(timeout=total + 30)
    except Exception:
        cap.kill()
        osa('tell application "Synthesia" to quit', run)
        raise
    osa('tell application "Synthesia" to quit', run)
    if cap.returncode != 0 or not out.exists() or out.stat().st_size < 100_000:
        raise RuntimeError("capture Synthesia échouée")
    return out, crop
