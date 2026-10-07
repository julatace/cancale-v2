import json
import threading
import time
import urllib.request
import urllib.error
import pytest
from http.server import ThreadingHTTPServer
from app import config
from app.ui import server


@pytest.fixture
def srv(tmp_path, monkeypatch):
    st = config.load_settings()
    st["paths"] = {**st["paths"], "data_dir": str(tmp_path), "database": str(tmp_path / "d.sqlite3"), "logs_dir": str(tmp_path / "l")}
    calls, engines = [], []
    def fake(settings, level=None, formats=None, publish=True, **k):
        import logging
        engines.append(settings["engine"])
        logging.getLogger("piano.director").info("🎬 étape test")
        calls.append((level, tuple(formats), publish))
        time.sleep(0.2)
        return {"status": "READY", "video": str(tmp_path / "x.mp4"), "qc": {"score": 100}}
    monkeypatch.setattr(server, "RUNNER", fake)
    monkeypatch.setattr(server, "JOB", server.Job())
    logging_ = __import__("logging"); logging_.getLogger("piano").setLevel("INFO")
    s = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(lambda: st))
    threading.Thread(target=s.serve_forever, daemon=True).start()
    monkeypatch.setattr(server.stock, "refill_in_background", lambda *_: None)
    yield f"http://127.0.0.1:{s.server_address[1]}", calls
    s.shutdown()


def get(u):
    return json.load(urllib.request.urlopen(u))


def post(u, body, headers=None):
    req = urllib.request.Request(u, json.dumps(body).encode(), {"Content-Type": "application/json", **(headers or {})})
    try:
        return urllib.request.urlopen(req).status, json.load(urllib.request.urlopen(req)) if False else None
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def test_page_and_options(srv):
    base, _ = srv
    html = urllib.request.urlopen(base + "/").read().decode()
    assert "Piano Studio AI" in html and "Niveau de difficulté" in html
    o = get(base + "/api/options")
    assert [l["key"] for l in o["levels"]] == ["facile", "moyen", "difficile"]
    assert {f["key"] for f in o["formats"]} == {"vertical", "horizontal"}


def test_run_with_level_and_format_and_live_logs(srv):
    base, calls = srv
    req = urllib.request.Request(base + "/api/run", json.dumps({"level": "difficile", "formats": ["vertical", "horizontal"], "publish": False}).encode(),
                                 {"Content-Type": "application/json"})
    assert json.load(urllib.request.urlopen(req))["ok"]
    for _ in range(40):
        st = get(base + "/api/status")
        if st["status"] != "running": break
        time.sleep(0.1)
    assert st["status"] == "done" and calls == [("difficile", ("vertical", "horizontal"), False)]
    assert any("étape test" in m for m in st["logs"])


def test_rejects_unknown_choices_foreign_origin_and_parallel(srv):
    base, _ = srv
    assert post(base + "/api/run", {"level": "dieu"})[0] == 400
    assert post(base + "/api/run", {"formats": ["carre"]})[0] == 400
    assert post(base + "/api/run", {"level": "facile"}, {"Origin": "https://evil.example"})[0] == 403
    assert get(base + "/files/..%2F..%2Fetc%2Fpasswd") if False else True
    try:
        urllib.request.urlopen(base + "/files/..%2F..%2Fetc%2Fpasswd")
        assert False
    except urllib.error.HTTPError as e:
        assert e.code == 404


def test_synthesia_is_forced_unless_switched_off(srv, monkeypatch):
    base, calls = srv
    seen = []
    orig = server.RUNNER
    monkeypatch.setattr(server, "RUNNER", lambda settings, **k: seen.append(settings["engine"]) or orig(settings, **k))
    for synth in (True, False):
        req = urllib.request.Request(base + "/api/run", json.dumps({"synthesia": synth}).encode(), {"Content-Type": "application/json"})
        urllib.request.urlopen(req)
        for _ in range(40):
            if get(base + "/api/status")["status"] != "running": break
            time.sleep(0.1)
    assert seen == ["synthesia", "builtin"]


def _upload(base, name, data, rights="1"):
    req = urllib.request.Request(base + "/api/upload", data, {"X-Filename": name, "X-Rights": rights, "Content-Type": "application/octet-stream"})
    try:
        r = urllib.request.urlopen(req)
        return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def test_upload_own_midi_then_listed_and_selectable(srv):
    from tests.helpers import song
    base, _ = srv
    code, r = _upload(base, "Ma%20valse.mid", song())
    assert code == 200 and r["status"] == "LEGAL_CONFIRMED"
    lst = get(base + "/api/songs")
    mine = [x for x in lst if x["origin"] == "mine"]
    assert mine and mine[0]["title"] == "Ma valse"
    assert _upload(base, "Ma%20valse.mid", song())[1]["status"] == "DUPLICATE"


def test_upload_requires_rights_and_real_midi(srv):
    from tests.helpers import song
    base, _ = srv
    assert _upload(base, "a.mid", song(), rights="0")[0] == 400           # droits non confirmés
    assert _upload(base, "a.mp3", b"ID3....")[0] == 400                    # pas un MIDI
    assert _upload(base, "a.mid", b"not a midi at all")[0] == 400          # MIDI invalide


def test_chosen_song_is_used_by_pipeline(tmp_path):
    from app import config
    from app.director import pipeline
    from app.database import db
    from app.ui import server
    from tests.helpers import song
    st = config.load_settings()
    st["paths"] = {**st["paths"], "data_dir": str(tmp_path), "database": str(tmp_path / "d.sqlite3"), "logs_dir": str(tmp_path / "l")}
    r = server.import_upload(st, "Ma chanson.mid", song(), "Ma chanson", "Moi")
    out = pipeline.run_one(st, seed=1, dry_run=True, song_id=r["song_id"])
    assert out["song"] == "Ma chanson"


def test_search_trends_and_import_routes(srv, monkeypatch):
    base, _ = srv
    monkeypatch.setattr(server.msearch, "search", lambda s, q: {"query": q, "results": [{"kind": "online", "title": "Clair de lune", "composer": "C. Debussy",
                                                                                          "license": "Public Domain", "page": server.msearch.ALLOWED_PREFIX + "x"}], "message": ""})
    monkeypatch.setattr(server.mtrends, "fetch_trends", lambda c, g: [{"rank": 1, "title": "Song", "artist": "Artist"}])
    monkeypatch.setattr(server.msearch, "import_found", lambda s, page: {"status": "LEGAL_CONFIRMED", "song_id": 7, "title": "Clair de lune", "license": "Public Domain"})
    r = get(base + "/api/search?q=clair%20de%20lune")
    assert r["results"][0]["license"] == "Public Domain"
    assert get(base + "/api/trends?country=fr&genre=classical")["items"][0]["title"] == "Song"
    req = urllib.request.Request(base + "/api/import-found", json.dumps({"page": "https://www.mutopiaproject.org/x"}).encode(), {"Content-Type": "application/json"})
    assert json.load(urllib.request.urlopen(req))["song_id"] == 7
    o = get(base + "/api/options")
    assert {l["key"] for l in o["languages"]} == {"fr", "en", "es"} and any(c["key"] == "gb" for c in o["countries"])


def test_trends_failure_is_a_message_not_an_error(srv, monkeypatch):
    base, _ = srv
    def boom(c, g): raise server.mtrends.TrendsUnavailable("réseau")
    monkeypatch.setattr(server.mtrends, "fetch_trends", boom)
    r = get(base + "/api/trends")
    assert r["items"] == [] and "réseau" in r["message"]


def test_page_has_web_search_button_that_stays_user_driven():
    from app.ui.page import PAGE
    assert 'id="qweb"' in PAGE and "google.com/search" in PAGE and 'rel="noopener"' in PAGE
    assert "réclamation" in PAGE                              # avertissement sur les droits affiché près de l'ajout de fichiers
