from datetime import date, datetime, timedelta, timezone

from app.database import db
from app.scheduler import queue


def _conn(tmp_path):
    c = db.connect(tmp_path / "t.sqlite3")
    db.add_song(c, "A", "x", "s", "LEGAL_CONFIRMED", hash="a")
    db.add_song(c, "B", "x", "s", "LEGAL_CONFIRMED", hash="b")
    for i, (song, style) in enumerate([(1, "facile|vertical"), (1, "facile|horizontal"), (2, "moyen|vertical")], 1):
        c.execute("INSERT INTO videos(song_id,style,duration,output_path,quality_score,status,title,meta,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                  (song, style, 60, f"/x/{i}.mp4", 95, "READY", f"V{i}", "{}", db.now()))
    c.commit()
    return c


def test_parse_times_and_slots():
    assert queue.parse_times("19h, 8h15; 12:30, nimp") == ["08:15", "12:30", "19:00"]
    sl = queue.slots(date(2030, 1, 6), 5, 2, ["12:30", "19:00", "22:00"], now=datetime(2030, 1, 1).astimezone())
    assert [(d.day, d.hour) for d in sl] == [(6, 12), (6, 19), (7, 12), (7, 19), (8, 12)]       # 2 par jour : la 3e heure est ignorée
    past = queue.slots(date(2020, 1, 1), 1, 1, ["12:00"])
    assert past[0] > datetime.now().astimezone()                                                 # jamais dans le passé


def test_short_and_long_of_same_song_share_a_slot(tmp_path):
    c = _conn(tmp_path)
    when = queue.slots(date(2030, 1, 6), 2, 2, ["12:30", "19:00"], now=datetime(2030, 1, 1).astimezone())
    out = queue.plan(c, [1, 2, 3], when)
    assert [o["run_at"] for o in out][0] == [o["run_at"] for o in out][1] != out[2]["run_at"]
    assert queue.unscheduled(c) == []
    assert queue.cancel(c, queue.listing(c)[0]["id"]) and len(queue.unscheduled(c)) == 1


def test_run_due_publishes_on_time_only_and_marks_missed(tmp_path):
    c = _conn(tmp_path)
    now = datetime(2030, 1, 6, 20, 0, tzinfo=timezone.utc)
    for vid, at in ((1, now - timedelta(minutes=5)), (2, now + timedelta(hours=1)), (3, now - timedelta(hours=30))):
        c.execute("INSERT INTO schedule(video_id,run_at,status,created_at) VALUES(?,?,'PENDING',?)", (vid, at.isoformat(), db.now()))
    c.commit()
    calls = []
    res = queue.run_due({}, c, now, publish=lambda s, cn, v: calls.append(v) or [{"platform": "tiktok", "status": "PUBLISHED", "detail": ""}])
    st = {r["video_id"]: r["status"] for r in queue.listing(c)}
    assert calls == [1] and st[1] == "DONE" and st[2] == "PENDING" and st[3] == "MISSED"
    assert queue.run_due({}, c, now, publish=lambda *a: calls.append("again")) == [] and calls == [1]       # rien n'est publié deux fois


def test_run_due_failure_is_recorded(tmp_path):
    c = _conn(tmp_path)
    now = datetime.now(timezone.utc)
    c.execute("INSERT INTO schedule(video_id,run_at,status,created_at) VALUES(1,?,'PENDING',?)", ((now - timedelta(minutes=1)).isoformat(), db.now()))
    c.commit()
    queue.run_due({}, c, now, publish=lambda *a: [{"platform": "tiktok", "status": "FAILED", "detail": "boom"}])
    x = queue.listing(c)[0]
    assert x["status"] == "FAILED" and "boom" in x["detail"]
