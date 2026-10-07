import subprocess
import threading
from types import SimpleNamespace as NS

import pytest
from app import config
from app.director import control
from app.synthesia_controller import mac

SCREENS = "[AVFoundation indev] AVFoundation video devices:\n[AVFoundation indev] [1] Capture screen 0\n[AVFoundation indev] AVFoundation audio devices:\n"


@pytest.fixture(autouse=True)
def clean():
    control.CANCEL.clear(); control.STOP_RECORD.clear()
    yield
    control.CANCEL.clear(); control.STOP_RECORD.clear()


def mk_run(tmp_path, ffmpeg_ok=True, hw_ok=True, hang=False, screencap_ok=True, usable="00:00:20.00"):
    log = []

    def run(cmd, **k):
        s = cmd[-1] if cmd[0] == "osascript" else ""
        log.append(cmd[0] if cmd[0] != "osascript" else s)
        if "-list_devices" in cmd: return NS(returncode=0, stdout="", stderr=SCREENS)
        if cmd[0] == "osascript":
            if "UI elements enabled" in s: return NS(returncode=0, stdout="true", stderr="")
            if "get autohide" in s: return NS(returncode=0, stdout="false", stderr="")
            if "get bounds" in s: return NS(returncode=0, stdout="0, 0, 1470, 956", stderr="")
            if "position, size" in s: return NS(returncode=0, stdout="400, 40, 500, 800", stderr="")
            return NS(returncode=0, stdout="", stderr="")
        if cmd[0] == "ffmpeg" and "-f" in cmd and "avfoundation" in cmd:
            if hang: raise subprocess.TimeoutExpired(cmd, 1)
            enc = cmd[cmd.index("-c:v") + 1]
            if not ffmpeg_ok or (enc == "h264_videotoolbox" and not hw_ok): return NS(returncode=1, stdout="", stderr="encoder error")
            open(cmd[-1], "wb").write(b"x" * 9000); return NS(returncode=0, stdout="", stderr="")
        if cmd[0] == "screencapture":
            if not screencap_ok: return NS(returncode=1, stdout="", stderr="denied")
            open(cmd[-1], "wb").write(b"x" * 9000); return NS(returncode=0, stdout="", stderr="")
        if cmd[0] == "ffmpeg" and "signalstats,metadata=print" in cmd: return NS(returncode=0, stdout="", stderr="lavfi.signalstats.YAVG=80.0")
        if cmd[0] == "ffmpeg": return NS(returncode=0, stdout="", stderr=f"frame=1 time={usable} bitrate=1")
        return NS(returncode=0, stdout="", stderr="")
    return run, log


def test_prefers_ffmpeg_hardware_then_software_then_screencapture(tmp_path):
    p = tmp_path / "p.mov"
    assert mac.pick_backend({}, mk_run(tmp_path)[0], p) == ("ffmpeg", "h264_videotoolbox")
    assert mac.pick_backend({}, mk_run(tmp_path, hw_ok=False)[0], p) == ("ffmpeg", "libx264")
    assert mac.pick_backend({}, mk_run(tmp_path, ffmpeg_ok=False)[0], p) == ("screencapture", None)
    assert mac.pick_backend({}, mk_run(tmp_path, hang=True)[0], p)[0] == "screencapture"      # ffmpeg figé -> repli
    with pytest.raises(RuntimeError, match="impossible"):
        mac.pick_backend({}, mk_run(tmp_path, ffmpeg_ok=False, screencap_ok=False)[0], p)


class FakeFfmpegCap:
    """Faux ffmpeg : ne s'arrête que si on lui écrit « q » (comme le vrai), puis laisse un fichier lisible."""
    def __init__(self, out): self.out = out; self.returncode = None; self.sent = []; self.stdin = self; self.stderr = None; self.polls = 0
    def write(self, b): self.sent.append(b); self.returncode = 0; open(self.out, "wb").write(b"x" * 200_000)
    def flush(self): pass
    def poll(self):
        self.polls += 1
        if self.polls == 3: control.STOP_RECORD.set()           # l'utilisateur clique « Arrêter l'enregistrement »
        return self.returncode
    def wait(self, timeout=None): return self.returncode
    def kill(self): self.returncode = -9


def test_stop_keeps_what_was_recorded_with_ffmpeg(tmp_path, monkeypatch):
    run, log = mk_run(tmp_path, usable="00:00:21.50")
    made = []
    monkeypatch.setattr(mac.subprocess, "Popen", lambda cmd, **k: made.append(FakeFfmpegCap(cmd[-1])) or made[-1])
    monkeypatch.setattr(mac.time, "sleep", lambda s: None)
    cfg = {**config.load_settings()["synthesia"], "capture_backend": "ffmpeg", "hide_dock": False}
    out, crop, recorded = mac.record(tmp_path / "a.mid", 60, tmp_path / "o.mov", cfg, run=run, sleep=lambda s: None)
    assert made[0].sent == [b"q"]                       # arrêt propre demandé à ffmpeg
    assert recorded == pytest.approx(21.5) and out.exists()


def test_stop_with_unusable_file_explains_instead_of_silently_losing(tmp_path, monkeypatch):
    run, _ = mk_run(tmp_path, ffmpeg_ok=False, usable="")                 # -> screencapture
    class Cap:
        returncode = None
        stderr = None
        n = 0
        def poll(self):
            Cap.n += 1
            if Cap.n == 3: control.STOP_RECORD.set()
            return self.returncode
        def send_signal(self, sig): self.returncode = -2                  # arrêté, mais aucun fichier écrit
        def wait(self, timeout=None): return self.returncode
        def kill(self): pass
    monkeypatch.setattr(mac.subprocess, "Popen", lambda cmd, **k: Cap())
    monkeypatch.setattr(mac.time, "sleep", lambda s: None)
    cfg = {**config.load_settings()["synthesia"], "capture_backend": "auto", "hide_dock": False}
    with pytest.raises(RuntimeError, match="pas été conservé"):
        mac.record(tmp_path / "a.mid", 60, tmp_path / "o2.mov", cfg, run=run, sleep=lambda s: None)
