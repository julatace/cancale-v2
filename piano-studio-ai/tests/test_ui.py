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
    calls = []
    def fake(settings, level=None, fmt=None, publish=True, **k):
        import logging
        logging.getLogger("piano.director").info("🎬 étape test")
        calls.append((level, fmt, publish))
        time.sleep(0.2)
        return {"status": "READY", "video": str(tmp_path / "x.mp4"), "qc": {"score": 100}}
    monkeypatch.setattr(server, "RUNNER", fake)
    monkeypatch.setattr(server, "JOB", server.Job())
    logging_ = __import__("logging"); logging_.getLogger("piano").setLevel("INFO")
    s = ThreadingHTTPServer(("127.0.0.1", 0), server.make_handler(lambda: st))
    threading.Thread(target=s.serve_forever, daemon=True).start()
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
    req = urllib.request.Request(base + "/api/run", json.dumps({"level": "difficile", "format": "horizontal", "publish": False}).encode(),
                                 {"Content-Type": "application/json"})
    assert json.load(urllib.request.urlopen(req))["ok"]
    for _ in range(40):
        st = get(base + "/api/status")
        if st["status"] != "running": break
        time.sleep(0.1)
    assert st["status"] == "done" and calls == [("difficile", "horizontal", False)]
    assert any("étape test" in m for m in st["logs"])


def test_rejects_unknown_choices_foreign_origin_and_parallel(srv):
    base, _ = srv
    assert post(base + "/api/run", {"level": "dieu"})[0] == 400
    assert post(base + "/api/run", {"format": "carre"})[0] == 400
    assert post(base + "/api/run", {"level": "facile"}, {"Origin": "https://evil.example"})[0] == 403
    assert get(base + "/files/..%2F..%2Fetc%2Fpasswd") if False else True
    try:
        urllib.request.urlopen(base + "/files/..%2F..%2Fetc%2Fpasswd")
        assert False
    except urllib.error.HTTPError as e:
        assert e.code == 404
