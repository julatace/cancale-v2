import threading
import time
import json
import urllib.request
from http.server import ThreadingHTTPServer
from types import SimpleNamespace as NS

import pytest
from app import config
from app.director import control
from app.synthesia_controller import mac
from app.ui import server
from app.midi_analyzer.parser import parse_midi
from app.visualizer import falling
from tests.helpers import song


@pytest.fixture(autouse=True)
def clean_flag():
    control.CANCEL.clear()
    yield
    control.CANCEL.clear()


def test_builtin_render_stops_on_cancel(tmp_path):
    notes, _ = parse_midi(song())
    control.CANCEL.set()
    with pytest.raises(control.Cancelled):
        falling.render_video(notes, 8, 5, tmp_path / "v.mp4", "t", "s", fps=15)


def test_record_cancel_quits_synthesia_and_restores_dock(tmp_path, monkeypatch):
    calls = []
    dock = {"hidden": False}

    def run(cmd, **k):
        s = cmd[-1] if cmd[0] == "osascript" else ""
        if "set autohide to true" in s: dock["hidden"] = True
        if "set autohide to false" in s: dock["hidden"] = False
        calls.append(s or cmd[0])
        if cmd[0] == "screencapture":
            (tmp_path / "preflight.mov").write_bytes(b"x" * 9000)
        if "get autohide" in s: return NS(returncode=0, stdout="true" if dock["hidden"] else "false", stderr="")
        if "UI elements enabled" in s: return NS(returncode=0, stdout="true", stderr="")
        if "get bounds" in s: return NS(returncode=0, stdout="0, 0, 1470, 956", stderr="")
        if "position, size" in s: return NS(returncode=0, stdout="400, 40, 500, 800", stderr="")
        if cmd[0] == "ffmpeg": return NS(returncode=0, stdout="", stderr="lavfi.signalstats.YAVG=90.0")
        return NS(returncode=0, stdout="", stderr="")

    class FakeCap:
        returncode = None
        def poll(self): return None
        def kill(self): calls.append("CAP_KILLED")
    monkeypatch.setattr(mac.subprocess, "Popen", lambda *a, **k: FakeCap())
    monkeypatch.setattr(mac.time, "sleep", lambda s: None)
    threading.Timer(0.3, control.CANCEL.set).start()
    cfg = {**config.load_settings()["synthesia"], "hide_dock": True}
    with pytest.raises(control.Cancelled):
        mac.record(tmp_path / "a.mid", 30, tmp_path / "o.mov", cfg, run=run, sleep=lambda s: None)
    assert "CAP_KILLED" in calls
    assert any('tell application "Synthesia" to quit' in c for c in calls)
    assert any("set autohide to false" in c for c in calls)            # Dock remis comme avant


def test_stop_endpoint_cancels_running_job(tmp_path, monkeypatch):
    st = config.load_settings()
    st["paths"] = {**st["paths"], "data_dir": str(tmp_path), "database": str(tmp_path / "d.sqlite3"), "logs_dir": str(tmp_path / "l")}

    def slow(settings, **k):
        for _ in range(200):
            control.check()
            time.sleep(0.05)
        return {"status": "READY"}
    monkeypatch.setattr(server, "RUNNER", slow)
    monkeypatch.setattr(server, "JOB", server.Job())
    monkeypatch.setattr(server.stock, "refill_in_background", lambda *_: None)
    s = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(lambda: st))
    threading.Thread(target=s.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{s.server_address[1]}"
    post = lambda p, b: json.load(urllib.request.urlopen(urllib.request.Request(base + p, json.dumps(b).encode(), {"Content-Type": "application/json"})))
    post("/api/run", {})
    time.sleep(0.3)
    assert post("/api/stop", {})["was_running"] is True
    for _ in range(40):
        st_ = json.load(urllib.request.urlopen(base + "/api/status"))
        if st_["status"] != "running": break
        time.sleep(0.1)
    s.shutdown()
    assert st_["status"] == "cancelled" and any("arrêtée" in m for m in st_["logs"])


def test_both_formats_last_at_least_one_minute_and_not_too_long():
    f = config.load_settings()["formats"]
    assert f["vertical"]["min_duration"] >= 60 and f["horizontal"]["min_duration"] >= 60
    assert f["horizontal"]["max_duration"] <= 180


def test_stop_recording_keeps_what_was_recorded(tmp_path):
    notes, _ = parse_midi(song())
    control.STOP_RECORD.set()                       # arrêt demandé dès le début : on garde au moins 5 s
    res = {}
    out = falling.render_video(notes, 8, 12, tmp_path / "v.mp4", "t", "s", fps=15, result=res)
    assert out.exists() and 4.9 <= res["duration"] < 12
    assert not control.STOP_RECORD.is_set()         # consommé : le format suivant enregistrera normalement


def test_pipeline_stopped_early_still_makes_a_valid_shorter_video(tmp_path):
    from app.director import pipeline
    st = config.load_settings()
    st["paths"] = {**st["paths"], "data_dir": str(tmp_path), "database": str(tmp_path / "d.sqlite3"), "logs_dir": str(tmp_path / "l")}
    st["duration_target"], st["duration_range"], st["engine"] = 12, [10, 14], "builtin"
    st["formats"]["vertical"]["min_duration"] = 0
    control.STOP_RECORD.set()
    r = pipeline.run_one(st, seed=3, publish=False, level="facile", fmt="vertical")
    assert r["status"] == "READY" and r["section"]["stopped_early"] and r["section"]["duration"] < 12 and r["qc"]["score"] >= 90


def test_stop_recording_endpoint(tmp_path, monkeypatch):
    st = config.load_settings()
    st["paths"] = {**st["paths"], "data_dir": str(tmp_path), "database": str(tmp_path / "d.sqlite3"), "logs_dir": str(tmp_path / "l")}
    seen = []
    def runner(settings, **k):
        for _ in range(100):
            if control.STOP_RECORD.is_set():
                seen.append("stop"); control.STOP_RECORD.clear(); break
            time.sleep(0.05)
        return {"status": "READY"}
    monkeypatch.setattr(server, "RUNNER", runner)
    monkeypatch.setattr(server, "JOB", server.Job())
    monkeypatch.setattr(server.stock, "refill_in_background", lambda *_: None)
    s = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(lambda: st))
    threading.Thread(target=s.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{s.server_address[1]}"
    post = lambda p, b: json.load(urllib.request.urlopen(urllib.request.Request(base + p, json.dumps(b).encode(), {"Content-Type": "application/json"})))
    post("/api/run", {})
    time.sleep(0.3)
    assert post("/api/stop-recording", {})["was_running"] is True
    for _ in range(40):
        if json.load(urllib.request.urlopen(base + "/api/status"))["status"] == "done": break
        time.sleep(0.1)
    s.shutdown()
    assert seen == ["stop"]
