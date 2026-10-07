"""Pilotage de l'app Synthesia achetée par l'utilisateur (macOS) : ouverture du MIDI, lecture, capture d'écran.
Aucune API Synthesia n'existe : AppleScript/System Events + ffmpeg avfoundation. Étalonné par `piano mac-check`."""
import logging
import signal
import platform
import shutil
import re
import subprocess
import time
from pathlib import Path


from app.director import control

log = logging.getLogger("piano.mac")


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
        ok1 = True
        if cfg.get("click_listen_card", False):
            ok1 = click(*card, run=run)
            sleep(0.7)
        ok2 = click(*cont, run=run)
        log.info("clic « Continuer » en %s (fenêtre %s)", cont, (x, y, w, _h))
        if ok1 and ok2:
            return f"click{cont}"
    r = osa('tell application "System Events" to key code 36', run)
    if r.returncode != 0:
        raise RuntimeError("impossible de piloter Synthesia : " + (r.stderr or "").strip()[:150])
    return "return"


def dock_autohide(value: bool | None = None, run=sh) -> bool | None:
    """Lit (value=None) ou règle le masquage automatique du Dock ; retourne l'ancien état."""
    r = osa('tell application "System Events" to tell dock preferences to get autohide', run)
    old = "true" in (r.stdout or "").lower() if r.returncode == 0 else None
    if value is not None and old is not None and value != old:
        osa(f'tell application "System Events" to tell dock preferences to set autohide to {"true" if value else "false"}', run)
    return old


def park_mouse(run=sh):
    """Écarte le curseur de la fenêtre (bord gauche de l'écran) pour qu'il n'apparaisse pas dans la vidéo."""
    try:
        sw, sh_ = screen_points(run)
        if shutil.which("cliclick"):
            run(["cliclick", f"m:2,{sh_ // 2}"])
        else:
            osa(f'tell application "System Events" to set position of mouse to {{2, {sh_ // 2}}}', run)
    except Exception:
        pass


def fit_window(cfg: dict, sw: int, sh_: int, W: int = 1080, H: int = 1920, top: int = 300) -> tuple[int, int, int, int]:
    """(x, y, largeur, hauteur) de la fenêtre pour que la zone visible (sans barre de titre ni d'outils) ait exactement le rapport
    de la zone « app » du montage (W x (H-top)), la plus grande possible dans l'écran -> aucune bande, aucun rognage."""
    y = cfg.get("window_top_points", 40)
    tb = cfg.get("titlebar_points", 24)
    keep = 1 - cfg.get("crop_toolbar_fraction", 0.12)
    ratio = W / (H - top)
    h = sh_ - y - cfg.get("portrait_margin_points", 6)
    w = int((h - tb) * keep * ratio)
    if w > sw:                                   # format large : limité par la largeur de l'écran
        w = sw
        h = int(w / ratio / keep) + tb
    return (sw - w) // 2, y, w, h


def portrait_size(cfg: dict, sw: int, sh_: int) -> tuple[int, int, int, int]:
    return fit_window(cfg, sw, sh_, 1080, 1920, 300)


def arrange_window_portrait(cfg: dict, run=sh, sleep=time.sleep, layout=(1080, 1920, 300)) -> tuple[int, int, int, int]:
    """Fenêtre Synthesia en portrait sur toute la hauteur de l'écran. Vérifie le résultat réel ; réessaie une fois."""
    sw, sh_ = screen_points(run)
    x, y, w, h = fit_window(cfg, sw, sh_, *layout)
    wide = layout[0] > layout[1]
    geo = (0, 0, 1, 1)
    for order in (("size", "pos"), ("pos", "size", "size")):
        for what in order:
            val = f"{{{w}, {h}}}" if what == "size" else f"{{{x}, {y}}}"
            prop = "size" if what == "size" else "position"
            osa(f'tell application "System Events" to tell process "Synthesia" to set {prop} of window 1 to {val}', run)
            sleep(0.4)
        geo = window_geometry(run)
        log.info("fenêtre Synthesia après redimensionnement : x=%s y=%s largeur=%s hauteur=%s (visé %sx%s)", *geo, w, h)
        if (geo[2] / max(geo[3], 1) > 1.1) == wide:
            return geo
    log.warning("la fenêtre Synthesia n'a pas pris la forme voulue (%sx%s) : le gros plan sera limité", geo[2], geo[3])
    return geo


def crop_fractions(cfg: dict, run=sh) -> tuple[float, float, float, float] | None:
    """Zone de la fenêtre Synthesia (sans barre de titre) en fractions de l'écran, pour recadrer la capture."""
    try:
        sw, sh_ = screen_points(run)
        x, y, w, h = window_geometry(run)
    except Exception:
        return None
    tb = cfg.get("titlebar_points", 24)
    content = h - tb
    bar = content * cfg.get("crop_toolbar_fraction", 0.12)   # barre d'outils + progression de Synthesia
    return (max(x, 0) / sw, (max(y, 0) + tb + bar) / sh_, min(w, sw) / sw, (content - bar) / sh_)


def debug_frames(video: Path, outdir: Path, times=(2, 8, 25), run=sh) -> list[Path]:
    outdir.mkdir(parents=True, exist_ok=True)
    out = []
    for t in times:
        f = outdir / f"{video.stem}_{t}s.jpg"
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", str(video), "-frames:v", "1", "-vf", "scale=1000:-2", str(f)])
        if f.exists(): out.append(f)
    return out


def record(midi: Path, duration: float, out: Path, cfg: dict, run=sh, sleep=time.sleep, layout=(1080, 1920, 300)) -> tuple[Path, tuple | None, float | None]:
    """Relance Synthesia sur le MIDI, clique « Continuer », capture l'écran.
    Retourne (capture, zone de recadrage, durée réellement enregistrée si l'utilisateur a arrêté avant la fin, sinon None)."""
    control.check()
    ok, why = accessibility_ok(run)
    if not ok:
        raise RuntimeError(f"Accessibilité non autorisée : {why}")
    backend = cfg.get("capture_backend", "screencapture")
    ok, why = rec_test(out.with_name("preflight.mov"), seconds=1, run=run, backend=backend)
    if not ok:
        raise RuntimeError(f"Enregistrement d'écran impossible : {why}")
    screen = screen_devices(run)[0][0] if backend == "ffmpeg" else None
    total = duration + cfg["lead_in_seconds"] + cfg["tail_seconds"]
    log.info("1/5 relance de Synthesia et ouverture du MIDI")
    osa('tell application "Synthesia" to quit', run)   # état propre à chaque vidéo
    sleep(2)
    run(["open", "-a", str(cfg["app_path"]), str(midi)])
    sleep(cfg["load_seconds"])
    log.info("2/5 démarrage de l'enregistrement d'écran (%.0f s)", total)
    cap = subprocess.Popen(_capture_cmd(backend, screen, total, out), stderr=subprocess.PIPE)
    dock_before = None
    stopped_after = None
    try:
        dock_before = dock_autohide(True, run) if cfg.get("hide_dock", True) else None   # Dock masqué (remis à la fin)
        sleep(1.0)
        log.info("3/5 lancement de la lecture")
        start_playback(cfg, run)            # la lecture démarre dans la fenêtre large (disposition connue)
        crop = None
        if cfg.get("portrait", True):
            try:
                log.info("4/5 fenêtre à la forme du format (gros plan)")
                arrange_window_portrait(cfg, run, layout=layout)   # gros plan : fenêtre à la forme du format
                sleep(1.5)
            except Exception as e:
                log.warning("redimensionnement impossible (%s) : fenêtre gardée telle quelle", e)
        crop = crop_fractions(cfg, run)
        log.info("5/5 enregistrement en cours...")
        t_start = time.monotonic()
        deadline = t_start + total + 30
        control.STOP_RECORD.clear()
        while cap.poll() is None:                       # attente interrompable par les boutons
            control.check()                             # « Annuler » : on jette tout
            if control.STOP_RECORD.is_set():            # « Arrêter l'enregistrement » : on garde ce qui est enregistré
                control.STOP_RECORD.clear()
                stopped_after = time.monotonic() - t_start
                log.info("■ Enregistrement arrêté à %.0f s : la vidéo sera montée avec ce qui est enregistré.", stopped_after)
                cap.send_signal(signal.SIGINT)          # termine proprement le fichier vidéo
                try:
                    cap.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    cap.kill()
                break
            if time.monotonic() > deadline:
                raise subprocess.TimeoutExpired("capture", total + 30)
            time.sleep(0.4)
    except Exception:
        cap.kill()
        osa('tell application "Synthesia" to quit', run)
        if dock_before is False:
            dock_autohide(False, run)
        raise
    osa('tell application "Synthesia" to quit', run)
    if dock_before is False:
        dock_autohide(False, run)                          # remet le Dock comme avant
    if (cap.returncode != 0 and stopped_after is None) or not out.exists() or out.stat().st_size < 100_000:
        err = (cap.stderr.read().decode()[-300:] if cap.stderr else "")
        raise RuntimeError(f"capture écran échouée (autorisation « Enregistrement de l'écran » pour le Terminal ?) {err}")
    return out, crop, stopped_after


def _capture_cmd(backend: str, screen_idx, seconds, out: Path) -> list[str]:
    if backend == "ffmpeg":
        return ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "avfoundation", "-framerate", "30",
                "-capture_cursor", "0", "-i", f"{screen_idx}:none", "-t", str(seconds), "-c:v", "libx264",
                "-preset", "ultrafast", "-crf", "16", "-pix_fmt", "yuv420p", str(out)]
    return ["screencapture", "-x", "-v", "-V", str(int(seconds)), str(out)]   # enregistreur vidéo intégré à macOS


def rec_test(out: Path, seconds=3, run=sh, backend="screencapture") -> tuple[bool, str]:
    """Teste uniquement l'enregistrement d'écran : fichier créé, taille, image non noire."""
    idx = None
    if backend == "ffmpeg":
        dev = screen_devices(run)
        if not dev:
            return False, "aucun écran capturable (ffmpeg avfoundation)"
        idx = dev[0][0]
    out.unlink(missing_ok=True)
    try:
        r = run(_capture_cmd(backend, idx, seconds, out), timeout=seconds + 20)
    except subprocess.TimeoutExpired:
        return False, ("l'enregistrement reste bloqué : macOS n'a pas accordé « Enregistrement de l'écran » au Terminal. "
                       "Réglages Système > Confidentialité et sécurité > Enregistrement de l'écran et audio système > activer Terminal, "
                       "puis Cmd+Q sur le Terminal et relancer")
    if r.returncode != 0 or not out.exists():
        return False, "l'enregistrement a échoué : " + (r.stderr or r.stdout or "").strip()[-300:] + " -> autorisez le Terminal dans Enregistrement de l'écran"
    s = run(["ffmpeg", "-hide_banner", "-i", str(out), "-vf", "signalstats,metadata=print", "-f", "null", "-"]).stderr
    ys = [float(v) for v in re.findall(r"lavfi.signalstats.YAVG=([\d.]+)", s)]
    if ys and max(ys) < 3:
        return False, "image entièrement noire -> l'autorisation « Enregistrement de l'écran » manque pour le Terminal (quittez-le avec Cmd+Q puis relancez)"
    return True, f"OK ({out.stat().st_size // 1000} ko)"
