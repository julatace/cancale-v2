"""Pilotage de l'app Synthesia achetée par l'utilisateur (macOS) : ouverture du MIDI, lecture, capture d'écran.
Aucune API Synthesia n'existe : AppleScript/System Events + ffmpeg avfoundation. Étalonné par `piano mac-check`."""
import platform
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
    r = osa('tell application "System Events" to return name of first process', run)
    res.append(("Accessibility (System Events)", r.returncode == 0, (r.stderr or "").strip()[:120]))
    dev = screen_devices(run)
    res.append(("Écran capturable (ffmpeg avfoundation)", bool(dev), ", ".join(d[1] for d in dev) or "ffmpeg absent ou aucun écran"))
    res.append(("Étalonnage fait", bool(cfg.get("calibrated")), "mettre synthesia.calibrated: true après vérification visuelle"))
    return res


def ready(cfg, run=sh, system=platform.system) -> bool:
    return all(ok for _, ok, _ in check(cfg, run, system))


def record(midi: Path, duration: float, out: Path, cfg: dict, run=sh, sleep=time.sleep) -> Path:
    """Ouvre le MIDI dans Synthesia, lance la lecture et capture l'écran pendant `duration`+marge."""
    screen = screen_devices(run)[0][0]
    total = duration + cfg["lead_in_seconds"] + cfg["tail_seconds"]
    sh(["open", "-a", str(cfg["app_path"]), str(midi)])
    sleep(cfg["load_seconds"])
    cap = subprocess.Popen(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "avfoundation", "-framerate", "30",
                            "-capture_cursor", "0", "-i", f"{screen}:none", "-t", str(total), "-c:v", "libx264",
                            "-preset", "ultrafast", "-crf", "16", "-pix_fmt", "yuv420p", str(out)], stderr=subprocess.PIPE)
    sleep(1.0)
    osa(f'tell application "System Events" to key code {cfg["play_key_code"]}', run)  # 49=espace, 36=entrée
    cap.wait(timeout=total + 30)
    osa('tell application "System Events" to key code 53', run)  # Échap : retour au menu
    if cap.returncode != 0 or not out.exists() or out.stat().st_size < 100_000:
        raise RuntimeError("capture Synthesia échouée")
    return out
