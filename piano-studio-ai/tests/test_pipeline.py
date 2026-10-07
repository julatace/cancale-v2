import json
import pytest
from app import config
from app.director import pipeline
from app.publisher.base import Outbox, Result
from app.publisher.youtube import YouTube
from app.quality_control import qc
from app.content_generator.generate import generate
from app.music_discovery import generator
from app.midi_analyzer.parser import parse_midi


@pytest.fixture
def s(tmp_path):
    st = config.load_settings()
    st["paths"] = {**st["paths"], "data_dir": str(tmp_path / "data"), "database": str(tmp_path / "db.sqlite3"),
                   "logs_dir": str(tmp_path / "logs")}
    st["duration_target"] = 4
    st["duration_range"] = [3, 6]
    return st


def test_generator_is_deterministic_and_parsable():
    a, _ = generator.compose(7); b, _ = generator.compose(7); c, _ = generator.compose(8)
    assert a == b and a != c
    notes, _ = parse_midi(a)
    assert len(notes) > 100
    for name in generator.PD_SONGS:
        assert parse_midi(generator.pd_song(name)[0])[0]


def test_content_varies_and_avoids_used_titles():
    song = {"title": "X", "artist": "Y"}
    first = generate(song, "Facile", 1, set())
    again = generate(song, "Facile", 1, {first["title"]})
    assert again["title"] != first["title"]


def test_dry_run_publishes_nothing(s):
    r = pipeline.run_one(s, seed=3, dry_run=True)
    assert r["status"] == "DRY_RUN" and "video" not in r


def test_full_run_records_video_and_survives_unconfigured_platforms(s, monkeypatch):
    for k in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    r = pipeline.run_one(s, seed=5)
    assert r["status"] == "READY" and r["qc"]["score"] >= 90
    plats = {p["platform"]: p["status"] for p in r["publications"]}
    assert plats["outbox"] == "EXPORTED" and plats["youtube"] == "NOT_CONFIGURED"


def test_failing_platform_does_not_block_others(s, monkeypatch):
    class Boom:
        platform = "boom"
        def publish(self, *a): raise RuntimeError("API down")
    monkeypatch.setattr(pipeline, "adapters", lambda st, fmt=None: [Boom(), Outbox(config.resolve(st, "data_dir") / "published")])
    r = pipeline.run_one(s, seed=6)
    assert [p["status"] for p in r["publications"]] == ["FAILED", "EXPORTED"]


def test_qc_rejects_missing_and_bad(tmp_path):
    assert qc.check(tmp_path / "nope.mp4")["score"] == 0
    assert qc.verdict(95) == "PUBLISH" and qc.verdict(85) == "AUTOFIX" and qc.verdict(50) == "REJECT"


def test_youtube_flow_with_fake_http(tmp_path, monkeypatch):
    for k, v in {"YOUTUBE_CLIENT_ID": "a", "YOUTUBE_CLIENT_SECRET": "b", "YOUTUBE_REFRESH_TOKEN": "c"}.items():
        monkeypatch.setenv(k, v)
    v = tmp_path / "v.mp4"; v.write_bytes(b"x" * 100)
    calls = []

    def http(req, timeout=0):
        calls.append(req.full_url)
        if "oauth2" in req.full_url: return 200, {}, json.dumps({"access_token": "T"}).encode()
        if "uploadType" in req.full_url: return 200, {"Location": "https://up/1"}, b""
        return 200, {}, json.dumps({"id": "abc123"}).encode()
    r = YouTube(http).publish(v, {"title": "t", "description": "d"}, "1")
    assert r.status == "PUBLISHED" and r.post_id == "abc123" and len(calls) == 3


def test_youtube_failure_is_reported_not_raised(tmp_path, monkeypatch):
    for k in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"):
        monkeypatch.setenv(k, "x")
    def http(*a, **k): raise OSError("réseau coupé")
    assert YouTube(http).publish(tmp_path / "v", {"title": "t", "description": "d"}, "1").status == "FAILED"


def test_forced_synthesia_failure_reports_error_once(s):
    s["engine"] = "synthesia"          # hors Mac : le moteur n'est pas prêt
    r = pipeline.run_one(s, seed=9, publish=False)
    assert r["status"] == "FAILED" and "Mac" in r["error"]


def test_horizontal_long_format_and_level_override(s):
    s["formats"]["horizontal"].update(max_duration=6, min_duration=0)      # court pour le test
    r = pipeline.run_one(s, seed=11, publish=False, level="difficile", fmt="horizontal")
    assert r["status"] == "READY" and r["format"] == "horizontal" and r["bpm"] == 130 and r["difficulty"] == "Difficile"
    import json, subprocess
    v = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=width,height", "-of", "json", r["video"]],
                                  capture_output=True, text=True).stdout)["streams"][0]
    assert (v["width"], v["height"]) == (1920, 1080) and r["qc"]["score"] >= 90


def test_easy_level_is_slower_than_hard(s):
    easy = pipeline.run_one(s, seed=21, dry_run=True, level="facile")
    hard = pipeline.run_one(s, seed=21, dry_run=True, level="difficile")
    assert easy["bpm"] < hard["bpm"] and easy["difficulty"] == "Facile"
