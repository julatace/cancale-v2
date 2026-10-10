import time

import pytest

from app import config
from app.database import db
from app.director import control
from app.publisher import tiktok_web as tw, youtube_web as yw
from app.scheduler import queue as q


@pytest.fixture(autouse=True)
def _clear():
    control.CANCEL.clear()
    yield
    control.CANCEL.clear()


def test_nap_reacts_to_stop_immediately():
    t = time.time()
    control.CANCEL.set()
    with pytest.raises(control.Cancelled):
        tw.nap(30)                                   # une attente de 30 s s'interrompt aussitôt
    assert time.time() - t < 1


def test_nap_sleeps_normally_when_not_stopped():
    t = time.time()
    tw.nap(0.3)
    assert 0.25 < time.time() - t < 1.5


def test_youtube_stop_before_final_click_is_retryable(monkeypatch):
    monkeypatch.setattr(yw, "post", lambda *a, **k: (_ for _ in ()).throw(control.Cancelled("stop")))
    r = yw.YouTubeWeb(publish=True).publish(__import__("pathlib").Path("x.mp4"), {"title": "T", "description": "d"}, "1")
    assert r.status == "FAILED" and "brouillon" in r.detail


def test_youtube_stop_after_final_click_is_uncertain(monkeypatch):
    def boom(*a, **k):
        tw.CLICKED["v"] = True
        raise control.Cancelled("stop")
    monkeypatch.setattr(yw, "post", boom)
    r = yw.YouTubeWeb(publish=True).publish(__import__("pathlib").Path("x.mp4"), {"title": "T", "description": "d"}, "1")
    assert r.status == "UNCERTAIN"


def test_tiktok_stop_states(monkeypatch):
    monkeypatch.setattr(tw, "post", lambda *a, **k: (_ for _ in ()).throw(control.Cancelled("stop")))
    assert tw.TikTokWeb(publish=True).publish(__import__("pathlib").Path("x.mp4"), {"tiktok_caption": "c"}, "1").status == "FAILED"

    def boom(*a, **k):
        tw.CLICKED["v"] = True
        raise control.Cancelled("stop")
    monkeypatch.setattr(tw, "post", boom)
    assert tw.TikTokWeb(publish=True).publish(__import__("pathlib").Path("x.mp4"), {"tiktok_caption": "c"}, "1").status == "UNCERTAIN"


def _db_with_uncertain(tmp_path):
    conn = db.connect(tmp_path / "t.db")
    mp4 = tmp_path / "v.mp4"
    mp4.write_bytes(b"x")
    conn.execute("INSERT INTO videos(id,output_path,status,title,created_at) VALUES(5,?,?,?,?)", (str(mp4), "READY", "Ma vidéo", "n"))
    conn.execute("INSERT INTO publications(video_id,platform,status,published_at) VALUES(5,'tiktok','SCHEDULED','n')")
    conn.execute("INSERT INTO publications(video_id,platform,status,published_at) VALUES(5,'youtube','SENDING','n')")
    conn.commit()
    return conn, mp4


def test_uncertain_listing_and_resolution(tmp_path):
    s = config.load_settings()
    s["paths"] = {**s["paths"], "data_dir": str(tmp_path)}
    s["storage"] = {"delete_after_publish": True}
    conn, mp4 = _db_with_uncertain(tmp_path)
    assert [(u["platform"], u["status"]) for u in q.uncertain(conn)] == [("youtube", "SENDING")]
    assert q.resolve_uncertain(s, conn, 5, "youtube", "retry") == "retry"          # pas en ligne : nouvel envoi autorisé
    assert q.uncertain(conn) == [] and conn.execute("SELECT status FROM publications WHERE platform='youtube'").fetchone() is None and mp4.exists()
    conn.execute("INSERT INTO publications(video_id,platform,status,published_at) VALUES(5,'youtube','UNCERTAIN','n')")
    conn.commit()
    assert q.resolve_uncertain(s, conn, 5, "youtube", "online") == "online"         # en ligne : comptée, fichier supprimé du Mac
    assert not mp4.exists() and conn.execute("SELECT status FROM videos WHERE id=5").fetchone()["status"] == "PUBLISHED"
    with pytest.raises(ValueError):
        q.resolve_uncertain(s, conn, 5, "youtube", "online")
