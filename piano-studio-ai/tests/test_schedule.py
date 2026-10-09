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


def test_agenda_slots_one_per_video_and_past_days_ignored():
    from datetime import date, datetime
    now = datetime(2030, 1, 6, 8, 0).astimezone()
    days = [{"date": "2030-01-05", "count": 3}, {"date": "2030-01-07", "count": 2}, {"date": "2030-01-06", "count": 1}, {"date": "2030-01-08", "count": 0},
            {"date": "2030-01-09", "count": 3}]
    sl = queue.slots_for_days(days, ["12:30", "19:00"], now=now)
    assert [(d.day, d.hour) for d in sl] == [(6, 12), (7, 12), (7, 19), (9, 9), (9, 12), (9, 19)]      # hier ignoré, 0 vidéo ignoré, 3 le même jour = 3 heures
    late = queue.slots_for_days([{"date": "2030-01-06", "count": 2}], ["07:00", "07:30"], now=now)          # aujourd'hui, heures déjà passées
    assert len(late) == 2 and late[0] - now < timedelta(minutes=5) and late[1] - late[0] == timedelta(minutes=15)   # elles partent dès que le montage est fini
    assert queue.slots_for_days([{"date": "2030-01-07", "count": 9}], None, now=now).__len__() == 6     # plafonné à 6 par jour


def test_agenda_endpoints_produce_and_plan(tmp_path, monkeypatch):
    import json, threading, urllib.request, urllib.error
    from datetime import date, timedelta
    from http.server import ThreadingHTTPServer
    from app import config
    from app.ui import server as sv
    st = config.load_settings()
    st["paths"] = {**st["paths"], "data_dir": str(tmp_path), "database": str(tmp_path / "d.sqlite3"), "logs_dir": str(tmp_path / "l")}
    runs = []
    monkeypatch.setattr(sv, "RUNNER", lambda settings, **k: runs.append(1) or {"videos": [{"video_id": len(runs), "status": "READY"}]})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), sv.make_handler(lambda: st))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    def post(path, body):
        req = urllib.request.Request(f"http://127.0.0.1:{httpd.server_address[1]}{path}", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
        try:
            r = urllib.request.urlopen(req); return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())
    d1, d2 = (date.today() + timedelta(days=k) for k in (2, 3))
    assert post("/api/week", {"days": [], "formats": ["vertical"]})[0] == 400                          # agenda vide : message clair
    assert post("/api/week", {"days": [{"date": d1.isoformat(), "count": 2}, {"date": d2.isoformat(), "count": 1}], "formats": ["vertical"], "synthesia": False})[0] == 200
    import time
    for _ in range(100):
        if sv.JOB.snapshot()["status"] != "running":
            break
        time.sleep(0.1)
    assert len(runs) == 3                                                                              # une création par vidéo demandée dans l'agenda
    httpd.shutdown()


def test_failed_creations_are_redone_and_only_new_videos_are_scheduled(tmp_path, monkeypatch):
    from datetime import date, timedelta
    from app import config
    from app.database import db
    from app.ui import server as sv
    st = config.load_settings()
    st["paths"] = {**st["paths"], "data_dir": str(tmp_path), "database": str(tmp_path / "d.sqlite3"), "logs_dir": str(tmp_path / "l")}
    conn = db.connect(tmp_path / "d.sqlite3")
    db.add_song(conn, "A", "x", "s", "LEGAL_CONFIRMED", hash="a")
    old = conn.execute("INSERT INTO videos(song_id,style,duration,output_path,quality_score,status,title,meta,created_at) VALUES(1,'facile|vertical',60,'x',95,'READY','ANCIENNE','{}',?)", (db.now(),)).lastrowid
    conn.commit()
    calls = []

    def runner(settings, **k):
        calls.append(1)
        if len(calls) == 2:
            return {"videos": [{"video_id": None, "status": "FAILED", "error": "contrôle qualité refusé"}], "status": "FAILED"}
        c = db.connect(tmp_path / "d.sqlite3")
        s_id = db.add_song(c, f"S{len(calls)}", "x", "s", "LEGAL_CONFIRMED", hash=f"h{len(calls)}")
        vid = c.execute("INSERT INTO videos(song_id,style,duration,output_path,quality_score,status,title,meta,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                        (s_id, "facile|vertical", 60, "x", 95, "READY", f"NEW{len(calls)}", "{}", db.now())).lastrowid
        c.commit()
        return {"videos": [{"video_id": vid, "status": "READY", "title": f"NEW{len(calls)}"}], "status": "READY"}
    monkeypatch.setattr(sv, "RUNNER", runner)
    day = (date.today() + timedelta(days=2)).isoformat()
    job = sv.Job()
    slots = queue.slots_for_days([{"date": day, "count": 2}], None)
    job._run(st, None, ["vertical"], False, 2, None, None, {"slots": slots, "immediate": False, "times": ["12:30", "19:00"]})
    assert job.state["status"] == "done" and len(calls) == 3                          # la création ratée a été refaite
    titles = [x["title"] for x in queue.listing(conn)]
    assert sorted(titles) == ["NEW1", "NEW3"] and "ANCIENNE" not in titles          # l'ancienne vidéo prête n'est pas reprogrammée
    assert len(job.state["planned"]) == 2


def test_cancel_all_pending_keeps_the_videos(tmp_path):
    c = _conn(tmp_path)
    when = queue.slots(date(2030, 1, 6), 3, 2, ["12:30", "19:00"], now=datetime(2030, 1, 1).astimezone())
    queue.plan(c, [1, 2, 3], when)
    assert len(queue.listing(c)) == 3 and queue.cancel_all_pending(c) == 3
    assert queue.listing(c) == [] and len(queue.unscheduled(c)) == 3                  # les vidéos sont toujours là, prêtes à être reprogrammées


def test_each_video_is_published_right_after_its_montage_and_stopping_keeps_what_was_done(tmp_path, monkeypatch):
    from datetime import date, timedelta
    from app import config
    from app.database import db
    from app.director import control
    from app.scheduler import queue as q
    from app.ui import server as sv
    st = config.load_settings()
    st["paths"] = {**st["paths"], "data_dir": str(tmp_path), "database": str(tmp_path / "d.sqlite3"), "logs_dir": str(tmp_path / "l")}
    conn = db.connect(tmp_path / "d.sqlite3")
    order, counter = [], [0]

    def runner(settings, **k):
        counter[0] += 1
        n = counter[0]
        if n == 3 and not k.get("_second"):
            raise control.Cancelled()                            # l'utilisateur arrête pendant la 3e création
        c = db.connect(tmp_path / "d.sqlite3")
        s_id = db.add_song(c, f"S{n}", "x", "s", "LEGAL_CONFIRMED", hash=f"h{n}")
        vid = c.execute("INSERT INTO videos(song_id,style,duration,output_path,quality_score,status,title,meta,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                        (s_id, "facile|vertical", 60, "x", 95, "READY", f"V{n}", "{}", db.now())).lastrowid
        c.commit(); order.append(("made", vid))
        return {"videos": [{"video_id": vid, "status": "READY", "title": f"V{n}"}], "status": "READY"}
    monkeypatch.setattr(sv, "RUNNER", runner)
    monkeypatch.setattr(q, "publish_video", lambda s, cn, vid: order.append(("published", vid)) or [{"platform": "tiktok", "status": "PUBLISHED", "detail": ""}])
    slots = q.slots_for_days([{"date": (date.today() + timedelta(days=3)).isoformat(), "count": 4}], None)
    job = sv.Job()
    job._run(st, None, ["vertical"], False, 4, None, None, {"slots": slots, "immediate": True, "times": []})
    assert job.state["status"] == "cancelled"
    assert order == [("made", 1), ("published", 1), ("made", 2), ("published", 2)]       # chaque vidéo part avant que la suivante ne soit fabriquée
    order.clear(); counter[0] = 10                                                          # 2e lot, sans publication immédiate : programmation au fil de l'eau
    job2 = sv.Job()
    job2._run(st, None, ["vertical"], False, 2, None, None, {"slots": slots[:2], "immediate": False, "times": []})
    assert job2.state["status"] == "done"
    c2 = db.connect(tmp_path / "d.sqlite3")
    assert len([x for x in q.listing(c2) if x["status"] == "PENDING"]) == 2                  # chaque vidéo programmée dès sa fabrication
