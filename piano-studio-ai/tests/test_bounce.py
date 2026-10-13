import math

from app.bounce import choreo
from app.midi_analyzer.parser import Note


def _notes(spec):
    return [Note(t, t + 0.3, p, 90, 0) for t, p in spec]


def test_onsets_keep_melody_and_drop_too_close():
    ns = _notes([(0, 60), (0.0, 72), (0.1, 64), (0.5, 67), (0.55, 70), (1.0, 65)])
    on = choreo.melody_onsets(ns, min_gap=0.16)
    assert [t for t, _ in on] == [0, 0.5, 1.0] and on[0][1] == 72            # accord : la plus aiguë ; trop proche : écartée


def test_ball_lands_exactly_on_each_platform_at_note_time():
    spec = [(1.0 + i * 0.37 + (0.2 if i % 3 == 0 else 0), 48 + (i * 5) % 30) for i in range(25)]
    hits = choreo.build(spec)
    for h in hits:
        x, y = choreo.ball_at(hits, h.t)
        assert abs(x - h.x) < 1e-6 and abs(y - h.y) < 1e-6                    # impact EXACT au temps de la note
        x2, y2 = choreo.ball_at(hits, h.t - 1e-4)
        x3, y3 = choreo.ball_at(hits, h.t + 1e-4)
        assert abs(x2 - x) < 1 and abs(y2 - y) < 3 and abs(x3 - x) < 1 and abs(y3 - y) < 3      # trajectoire continue


def test_bounce_height_is_constant_and_path_descends():
    spec = [(1 + i * 0.5 + (i % 4) * 0.13, 55 + (i * 3) % 20) for i in range(20)]
    hits = choreo.build(spec, h=95, drop=150)
    for a, b in zip(hits, hits[1:]):
        steps = 60
        top = min(choreo.ball_at(hits, a.t + (b.t - a.t) * k / steps)[1] for k in range(steps + 1))
        assert abs((a.y - top) - 95) < 4                                      # le rebond monte toujours d'environ la même hauteur
        assert b.y > a.y                                                      # le parcours descend : la caméra peut suivre vers le bas
    assert all(-0.7 <= h.tilt <= 0.7 for h in hits)


def test_x_stays_on_screen_and_empty_input():
    spec = [(i * 0.4, 30 + (i * 7) % 60) for i in range(40)]
    hits = choreo.build(spec, width=1080, margin=150)
    assert all(150 <= h.x <= 930 for h in hits) and choreo.build([]) == []


def test_audit_midi_scores_good_and_bad(tmp_path):
    import random
    import struct
    from app.midi_analyzer import audit
    from app.midi_analyzer.writer import make_midi
    good = make_midi([(i * 0.5, 0.4, 55 + (i * 3) % 20, 90) for i in range(140)], bpm=120)
    tiny = make_midi([(0, 1, 60, 90), (1, 1, 64, 90)], bpm=120)
    (tmp_path / "bon.mid").write_bytes(good)
    (tmp_path / "court.mid").write_bytes(tiny)
    (tmp_path / "casse.mid").write_bytes(b"pas du midi")
    res = {r["file"]: r for r in audit.audit_folder(tmp_path)}
    assert res["bon.mid"]["score"] >= 85 and res["bon.mid"]["verdict"] in ("très bon", "bon")
    assert res["court.mid"]["verdict"] == "à éviter" and any("court" in i or "peu de notes" in i for i in res["court.mid"]["issues"])
    assert res["casse.mid"]["score"] == 0 and any("illisible" in i for i in res["casse.mid"]["issues"])
    assert list(res)[0] or True


def test_pair_uses_same_notes_and_section_as_piano(tmp_path, monkeypatch):
    """La vidéo « billes » du même morceau reçoit EXACTEMENT les notes et le passage du piano (donc le même son)."""
    from app import bounce, config
    from app.database import db
    seen = {}

    def fake_render_for(s, conn, sid, notes, sec, onsets, meta, lang, seed, publish=False):
        seen.update(notes=notes, sec=sec, onsets=onsets)
        return {"status": "READY", "video_id": 9, "format": "bounce", "title": "t"}
    monkeypatch.setattr(bounce, "render_for", fake_render_for)
    notes = [Note(i * 0.5, i * 0.5 + 0.4, 55 + i % 12, 90, 0) for i in range(80)]
    s = config.load_settings()
    r = bounce.make_pair(s, None, 1, notes, {"start": 5.0, "end": 35.0}, {"title": "X", "artist": "Y"}, "fr", 3)
    assert r["format"] == "bounce" and seen["notes"] is notes and seen["sec"] == {"start": 5.0, "end": 35.0}
    assert seen["onsets"][0][0] >= 0 and all(0 <= t < 30 for t, _ in seen["onsets"])
    assert bounce.make_pair(s, None, 1, notes[:5], {"start": 0.0, "end": 3.0}, {"title": "X"}, "fr", 3) is None        # trop peu de notes : ignorée


def test_agenda_slots_piano_then_bounce(monkeypatch):
    import time
    from datetime import datetime, timedelta
    from app.ui import server
    from app.scheduler import queue as sq
    calls = []
    monkeypatch.setattr(sq, "publish_video", lambda s, conn, vid, publish_at=None: calls.append((vid, publish_at)) or [{"platform": "tiktok", "status": "SCHEDULED", "detail": ""}])
    monkeypatch.setattr(sq, "native_time", lambda t: t)

    def pair(settings, **k):
        return {"status": "READY", "videos": [{"video_id": 1, "status": "READY", "format": "vertical", "title": "piano"},
                                              {"video_id": 2, "status": "READY", "format": "bounce", "title": "billes"}]}
    monkeypatch.setattr(server, "RUNNER", pair)
    from app import config
    s = config.load_settings()
    base = (datetime.now().astimezone() + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
    slots = [base, base + timedelta(hours=7)]
    job = server.Job()
    assert job.start(s, None, ["vertical"], False, 2, None, None, {"slots": slots, "immediate": False, "times": ["12:00"]})
    for _ in range(100):
        if job.state["status"] != "running":
            break
        time.sleep(0.1)
    assert job.state["status"] == "done" and calls == [(1, slots[0]), (2, slots[1])]        # piano au 1er créneau, billes au 2e : un seul morceau, deux créneaux


def test_wanted_combinations():
    from app import bounce
    assert bounce.wanted({}) == (True, False)
    assert bounce.wanted({"produce": {"piano": True, "bounce": True}}) == (True, True)
    assert bounce.wanted({"produce": {"piano": False, "bounce": True}}) == (False, True)
    assert bounce.wanted({"produce": {"piano": False, "bounce": False}}) == (True, False)       # jamais « rien » : le piano reste
    assert bounce.wanted({"bounce": {"with_piano": True}}) == (True, True)                       # ancien réglage compris


def test_publish_to_filters_platforms(tmp_path):
    from app import config
    from app.publisher import adapters
    s = config.load_settings()
    s["paths"] = {**s["paths"], "data_dir": str(tmp_path)}
    names = lambda st: [a.platform for a in adapters(st, fmt="vertical") if a.platform in ("tiktok", "youtube")]
    both = names({**s, "publish_to": {"tiktok": True, "youtube": True}})
    assert "tiktok" in both and "youtube" in both
    assert names({**s, "publish_to": {"tiktok": True, "youtube": False}}) == ["tiktok"]
    assert names({**s, "publish_to": {"tiktok": False, "youtube": True}}) == ["youtube"]


def test_runner_skips_piano_when_only_bounce_wanted(monkeypatch):
    from app import bounce, config
    from app.director import pipeline
    from app.ui import server
    calls = []
    monkeypatch.setattr(bounce, "run_one", lambda s, **k: calls.append("bounce") or {})
    monkeypatch.setattr(pipeline, "run_one", lambda s, **k: calls.append("piano") or {})
    s = config.load_settings()
    server._default_runner({**s, "produce": {"piano": False, "bounce": True}})
    server._default_runner({**s, "produce": {"piano": True, "bounce": True}})
    assert calls == ["bounce", "piano"]


def test_setting_endpoint_requires_at_least_one(tmp_path, monkeypatch):
    import json
    import threading
    import urllib.error
    import urllib.request
    from http.server import ThreadingHTTPServer
    from app import config
    from app.ui import server
    saved = {}
    monkeypatch.setattr(config, "save_local", lambda k, v: saved.update({k: v}))
    st = config.load_settings()
    st["paths"] = {**st["paths"], "data_dir": str(tmp_path), "database": str(tmp_path / "d.sqlite3"), "logs_dir": str(tmp_path / "l")}
    srv = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(lambda: st))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def post(body):
        req = urllib.request.Request(base + "/api/setting", json.dumps(body).encode(), {"Content-Type": "application/json"})
        try:
            return urllib.request.urlopen(req).status
        except urllib.error.HTTPError as e:
            return e.code
    try:
        assert post({"key": "publish_to", "value": {"tiktok": False, "youtube": False}}) == 400
        assert post({"key": "produce", "value": {"piano": False, "bounce": False}}) == 400
        assert post({"key": "publish_to", "value": {"tiktok": True, "youtube": False}}) == 200 and saved["publish_to"] == {"tiktok": True, "youtube": False}
        assert post({"key": "produce", "value": {"piano": False, "bounce": True}}) == 200 and saved["produce"] == {"piano": False, "bounce": True}
    finally:
        srv.shutdown()


def _pub_db(tmp_path, style):
    from app.database import db
    conn = db.connect(tmp_path / "p.db")
    mp4 = tmp_path / "v.mp4"
    mp4.write_bytes(b"x")
    conn.execute("INSERT INTO videos(id,output_path,style,status,title,meta,created_at) VALUES(1,?,?,?,?,?,?)", (str(mp4), style, "READY", "T", "{}", "n"))
    conn.commit()
    return conn


def test_bounce_videos_use_the_other_chrome_profile(tmp_path, monkeypatch):
    from app import config
    from app.scheduler import queue as q
    seen = []

    class Spy:
        def __init__(self, platform, profile):
            self.platform, self.profile = platform, profile

        def publish(self, video, meta, key):
            from app.publisher.base import Result
            seen.append((self.platform, self.profile))
            return Result(self.platform, "SCHEDULED", key, "ok")
    import app.publisher as pub
    monkeypatch.setattr(pub, "adapters", lambda s2, fmt=None: [Spy("tiktok", s2["tiktok"].get("chrome_profile")), Spy("youtube", s2["youtube"].get("chrome_profile"))])
    s = config.load_settings()
    s["paths"] = {**s["paths"], "data_dir": str(tmp_path)}
    s["storage"] = {"delete_after_publish": False}
    s["bounce"] = {"chrome_profile": "compte lola"}
    q.publish_video(s, _pub_db(tmp_path, "bounce|vertical"), 1)
    assert seen == [("tiktok", "compte lola"), ("youtube", "compte lola")]
    seen.clear()
    q.publish_video(s, _pub_db(tmp_path / "x" if (tmp_path / "x").mkdir() is None else tmp_path, "moyen|vertical"), 1)
    assert all(p != "compte lola" for _, p in seen)                                  # le piano garde son propre compte


def test_youtube_limit_is_per_account(tmp_path):
    from app import config
    from app.database import db
    from app.scheduler import queue as q
    s = config.load_settings()
    s["youtube"] = {**s.get("youtube", {}), "max_uploads_per_day": 2}
    conn = db.connect(tmp_path / "c.db")
    for vid, style in ((1, "moyen|vertical"), (2, "moyen|vertical"), (3, "bounce|vertical")):
        conn.execute("INSERT INTO videos(id,style,status,created_at) VALUES(?,?,?,?)", (vid, style, "READY", "n"))
        conn.execute("INSERT INTO publications(video_id,platform,status,published_at) VALUES(?,?,?,?)", (vid, "youtube", "SCHEDULED", db.now()))
    conn.commit()
    s["bounce"] = {"chrome_profile": "compte lola"}
    assert q.youtube_capacity(s, conn, "main") == 0 and q.youtube_capacity(s, conn, "bounce") == 1       # chaque compte a sa limite
    s["bounce"] = {}
    assert q.youtube_capacity(s, conn, "bounce") == 0                                                   # même compte : limite commune


def test_tabs_are_kept_per_profile():
    from app.publisher import tiktok_web as tw
    import inspect
    assert 'f"{PROFILE}|{site}"' in inspect.getsource(tw.open_url)
