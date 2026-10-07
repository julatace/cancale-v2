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
    st["duration_target"], st["duration_range"], st["engine"] = 8, [6, 10], "auto"
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
    st["duration_target"], st["duration_range"], st["engine"] = 8, [6, 10], "auto"
    st["formats"]["vertical"]["min_duration"] = 0
    n = []
    monkeypatch.setattr(mac, "ready", lambda cfg, *a, **k: True)
    monkeypatch.setattr(mac, "record", lambda midi, duration, out, cfg, **k: (n.append(1), shutil.copy(fake_capture, out), (out, None, None))[2])
    monkeypatch.setattr(mac, "debug_frames", lambda *a, **k: [])
    r = pipeline.run_one(st, seed=5, publish=False, formats=["vertical"])
    assert len(n) == 1 and r["status"] == "READY" and r["engine"] == "synthesia"
