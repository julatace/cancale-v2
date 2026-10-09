import json
import shutil
import subprocess

import pytest
from app import config
from app.director import pipeline
from app.synthesia_controller import mac


def probe(path):
    o = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height:format=duration", "-of", "json", str(path)],
                       capture_output=True, text=True).stdout
    j = json.loads(o)
    return j["streams"][0]["width"], j["streams"][0]["height"], float(j["format"]["duration"])


@pytest.fixture
def fake_capture(tmp_path):
    """Faux enregistrement de Synthesia (fenêtre verticale) : image animée, et une 'touche allumée' dans le bas à t = 8,0 s."""
    cap = tmp_path / "fake_cap.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "testsrc2=size=540x900:rate=30:duration=40,drawbox=x=0:y=720:w=540:h=180:color=white@0.9:t=fill:enable='gte(t,8)'",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(cap)], check=True)
    return cap


def test_one_recording_gives_vertical_and_horizontal(tmp_path, fake_capture, monkeypatch):
    st = config.load_settings()
    st["paths"] = {**st["paths"], "data_dir": str(tmp_path / "data"), "database": str(tmp_path / "d.sqlite3"), "logs_dir": str(tmp_path / "l")}
    st["duration_target"], st["duration_range"], st["engine"], st["style"] = 8, [6, 10], "auto", "synthesia"
    st["formats"]["vertical"]["min_duration"] = 0
    st["formats"]["horizontal"].update(max_duration=14, min_duration=0)
    calls = []

    def fake_record(midi, duration, out, cfg, run=None, sleep=None, layout=None):
        calls.append(duration)
        shutil.copy(fake_capture, out)
        return out, None, None

    monkeypatch.setattr(mac, "ready", lambda cfg, *a, **k: True)
    monkeypatch.setattr(mac, "record", fake_record)
    monkeypatch.setattr(mac, "debug_frames", lambda *a, **k: [])
    r = pipeline.run_one(st, seed=4, publish=False, level="moyen", formats=["vertical", "horizontal"])
    assert len(calls) == 1, "un seul enregistrement attendu"
    assert r["status"] == "READY" and len(r["videos"]) == 2
    by = {v["format"]: v for v in r["videos"]}
    assert by["vertical"]["engine"] == by["horizontal"]["engine"] == "synthesia"
    w, h, d = probe(by["vertical"]["video"]); assert (w, h) == (1080, 1920) and 6 <= d <= 9
    w, h, d = probe(by["horizontal"]["video"]); assert (w, h) == (1920, 1080) and 11 <= d <= 15
    assert by["vertical"]["qc"]["score"] >= 90 and by["horizontal"]["qc"]["score"] >= 90
    assert calls[0] >= 12                        # l'enregistrement couvre le format le plus long


def test_vertical_only_still_records_once(tmp_path, fake_capture, monkeypatch):
    st = config.load_settings()
    st["paths"] = {**st["paths"], "data_dir": str(tmp_path / "data"), "database": str(tmp_path / "d.sqlite3"), "logs_dir": str(tmp_path / "l")}
    st["duration_target"], st["duration_range"], st["engine"], st["style"] = 8, [6, 10], "auto", "synthesia"
    st["formats"]["vertical"]["min_duration"] = 0
    n = []
    monkeypatch.setattr(mac, "ready", lambda cfg, *a, **k: True)
    monkeypatch.setattr(mac, "record", lambda midi, duration, out, cfg, **k: (n.append(1), shutil.copy(fake_capture, out), (out, None, None))[2])
    monkeypatch.setattr(mac, "debug_frames", lambda *a, **k: [])
    r = pipeline.run_one(st, seed=5, publish=False, formats=["vertical"])
    assert len(n) == 1 and r["status"] == "READY" and r["engine"] == "synthesia"


def test_recording_is_capped_at_one_minute_thirty():
    from app import config
    from app.director import pipeline
    s = config.load_settings()
    s["engine"], s["style"] = "synthesia", "synthesia"
    assert s["synthesia"]["max_record_seconds"] == 90 and pipeline.record_cap(s) == 80          # 90 s au total - 8 s d'attente - 2 s de fin
    long_piece = {"duration": 400}
    assert pipeline._target(s["formats"]["horizontal"], s, long_piece) == 80                     # vidéo longue : coupée à 80 s de musique
    assert pipeline._target(s["formats"]["vertical"], s, long_piece) == s["duration_target"] <= 80
    s["engine"] = "builtin"
    assert pipeline._target(s["formats"]["horizontal"], s, long_piece) == s["formats"]["horizontal"]["max_duration"]   # rendu intégré : pas de limite d'écran


def test_mac_record_never_captures_more_than_the_limit(monkeypatch, tmp_path):
    from app.synthesia_controller import mac
    seen = {}
    monkeypatch.setattr(mac, "accessibility_ok", lambda run: (True, ""))
    monkeypatch.setattr(mac, "pick_backend", lambda *a, **k: ("screencapture", None))
    monkeypatch.setattr(mac, "_capture_cmd", lambda backend, screen, total, out, enc: seen.setdefault("total", total) and ["true"])
    monkeypatch.setattr(mac.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("stop ici")))
    cfg = {"lead_in_seconds": 8, "tail_seconds": 2, "load_seconds": 0, "app_path": "x", "max_record_seconds": 90}
    try:
        mac.record(tmp_path / "a.mid", 400, tmp_path / "o.mov", cfg, run=lambda *a, **k: type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(), sleep=lambda s: None)
    except Exception:
        pass
    assert seen["total"] == 90


def test_recording_is_cut_when_the_limit_is_reached_even_if_the_tool_keeps_going(monkeypatch, tmp_path):
    from app.synthesia_controller import mac
    clock = {"t": 1000.0}

    class FakeCap:
        returncode = 0
        stdin = None
        stderr = None
        def poll(self): return None                      # l'outil de capture ne s'arrête jamais tout seul
    stopped = []
    monkeypatch.setattr(mac, "accessibility_ok", lambda run: (True, ""))
    monkeypatch.setattr(mac, "pick_backend", lambda *a, **k: ("ffmpeg", "libx264"))
    monkeypatch.setattr(mac, "screen_devices", lambda run: [("1", "screen")])
    monkeypatch.setattr(mac, "_capture_cmd", lambda *a, **k: ["true"])
    monkeypatch.setattr(mac.subprocess, "Popen", lambda *a, **k: FakeCap())
    monkeypatch.setattr(mac, "start_playback", lambda *a, **k: None)
    monkeypatch.setattr(mac, "maximize_window", lambda *a, **k: None)
    monkeypatch.setattr(mac, "crop_fractions", lambda *a, **k: None)
    monkeypatch.setattr(mac, "dock_autohide", lambda *a, **k: None)
    monkeypatch.setattr(mac, "osa", lambda *a, **k: "")
    monkeypatch.setattr(mac, "_stop_capture", lambda cap, backend: stopped.append(clock["t"]))
    monkeypatch.setattr(mac, "_usable_seconds", lambda *a, **k: 92.0)
    monkeypatch.setattr(mac.time, "monotonic", lambda: clock["t"])
    monkeypatch.setattr(mac.time, "sleep", lambda s: clock.__setitem__("t", clock["t"] + s))
    out = tmp_path / "o.mov"; out.write_bytes(b"x" * 200_000)
    cfg = {"lead_in_seconds": 8, "tail_seconds": 2, "load_seconds": 6, "app_path": "x", "max_record_seconds": 90, "portrait": False}
    cap, crop, recorded = mac.record(tmp_path / "a.mid", 400, out, cfg, run=lambda *a, **k: type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})(), sleep=lambda s: clock.__setitem__("t", clock["t"] + s))
    assert recorded == 92.0 and len(stopped) == 1 and 90 <= stopped[0] - 1008.0 <= 96       # coupé 93 s après le début de la capture (1 min 30 + 3 s de marge), pas 4 minutes


def test_sketch_style_never_uses_synthesia(monkeypatch):
    from app.director import pipeline
    called = []
    monkeypatch.setattr(pipeline.mac, "ready", lambda cfg: called.append(1) or True)
    monkeypatch.setattr(pipeline, "_synthesia_batch", lambda *a, **k: called.append("batch") or [])
    monkeypatch.setattr(pipeline, "_produce", lambda *a, **k: {"ok": True})
    s = {"style": "sketch", "engine": "auto", "synthesia": {}, "keyboard": {"lowest_key": 36}}
    out = pipeline._make_videos(s, None, 1, "Facile", [("vertical", {}, {}, {}, {})], [], [], {}, {}, False, None)
    assert out == [{"ok": True}] and "batch" not in called
