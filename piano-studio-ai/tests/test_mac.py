import plistlib
import subprocess
import shutil
from types import SimpleNamespace as NS
from pathlib import Path
import pytest
from app.midi_analyzer.parser import parse_midi
from app.midi_analyzer.writer import trim_midi
from app.renderer import compose
from app.scheduler import launchd
from app.synthesia_controller import mac
from tests.helpers import song

CFG = {"app_path": "/nonexistent/Synthesia.app", "calibrated": False}


def test_not_ready_on_linux():
    assert not mac.ready(CFG)
    assert mac.check(CFG, system=lambda: "Linux")[0][1] is False


def test_check_on_mac_with_mocked_tools(tmp_path):
    app = tmp_path / "Synthesia.app"; app.mkdir()
    err = "[AVFoundation indev] AVFoundation video devices:\n[AVFoundation indev] [0] FaceTime HD\n[AVFoundation indev] [1] Capture screen 0\n[AVFoundation indev] AVFoundation audio devices:\n"
    run = lambda cmd, **k: NS(returncode=0, stdout="", stderr=err)
    res = mac.check({"app_path": str(app), "calibrated": True}, run=run, system=lambda: "Darwin")
    assert all(ok for _, ok, _ in res)
    assert mac.screen_devices(run) == [(1, "Capture screen 0")]


def test_not_ready_if_accessibility_denied(tmp_path):
    app = tmp_path / "S.app"; app.mkdir()
    run = lambda cmd, **k: NS(returncode=1 if cmd[0] == "osascript" else 0, stdout="", stderr="[1] Capture screen 0" if cmd[0] != "osascript" else "not allowed")
    assert not mac.ready({"app_path": str(app), "calibrated": True}, run=run, system=lambda: "Darwin")


def test_trim_midi_shifts_to_zero():
    notes, _ = parse_midi(song())
    n2, _ = parse_midi(trim_midi(notes, 8, 18))
    assert n2 and min(n.start for n in n2) < 0.6 and max(n.end for n in n2) <= 10.1


def test_launchd_plist():
    d = plistlib.loads(launchd.build_plist(["09:00", "19:00"], Path("/x"), python="/usr/bin/python3"))
    assert d["StartCalendarInterval"] == [{"Hour": 9, "Minute": 0}, {"Hour": 19, "Minute": 0}]


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg")
def test_compose_vertical_from_fake_capture(tmp_path):
    cap, wav = tmp_path / "c.mp4", tmp_path / "a.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=30:duration=6", "-c:v", "libx264", str(cap)], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=330:duration=4", str(wav)], check=True)
    out = compose.compose_vertical(cap, wav, tmp_path / "o.mp4", 1, 4, "Test title")
    from app.quality_control import qc
    assert qc.check(out, dur_range=(3, 6))["score"] >= 70
