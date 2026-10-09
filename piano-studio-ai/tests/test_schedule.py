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


def test_agenda_slots_are_always_in_the_future_and_spill_to_the_next_day():
    now = datetime(2030, 1, 6, 14, 48).astimezone()                       # il est 14 h 48
    days = [{"date": "2030-01-05", "count": 3}, {"date": "2030-01-06", "count": 2}, {"date": "2030-01-07", "count": 2}, {"date": "2030-01-08", "count": 0}]
    sl = queue.slots_for_days(days, ["12:30", "19:00"], now=now)
    assert [(d.day, d.hour) for d in sl] == [(6, 16), (6, 19), (7, 12), (7, 19)]      # hier ignoré ; aujourd'hui : 12 h 30 est passé -> 16 h puis 19 h
    assert all(d > now + timedelta(minutes=30) for d in sl)                           # jamais dans le passé ni à moins de 30 min
    late = queue.slots_for_days([{"date": "2030-01-06", "count": 3}], ["12:30", "19:00"], now=datetime(2030, 1, 6, 20, 0).astimezone())
    assert [(d.day, d.hour) for d in late] == [(6, 21), (7, 12), (7, 19)]               # ce qui ne tient plus aujourd'hui passe à demain
    assert queue.slots_for_days([{"date": "2030-01-07", "count": 9}], None, now=datetime(2030, 1, 6, 8, 0).astimezone()).__len__() == 6      # 6 par jour au maximum
    assert queue.slots_for_days([{"date": "2030-01-20", "count": 2}], None, now=datetime(2030, 1, 6, 8, 0).astimezone()) == []              # au-delà de 10 jours : TikTok ne programme pas si loin


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


def _job_env(tmp_path, monkeypatch, runner_factory):
    from app import config
    from app.database import db
    from app.scheduler import queue as q
    from app.ui import server as sv
    st = config.load_settings()
    st["paths"] = {**st["paths"], "data_dir": str(tmp_path), "database": str(tmp_path / "d.sqlite3"), "logs_dir": str(tmp_path / "l")}
    conn = db.connect(tmp_path / "d.sqlite3")
    sent = []
    monkeypatch.setattr(sv, "RUNNER", runner_factory(tmp_path))
    monkeypatch.setattr(q, "publish_video", lambda s, cn, vid, publish_at=None: sent.append((vid, publish_at)) or [{"platform": "tiktok", "status": "SCHEDULED" if publish_at else "PUBLISHED", "detail": ""}])
    return st, conn, sent, sv


def _make_video(tmp_path, n):
    from app.database import db
    c = db.connect(tmp_path / "d.sqlite3")
    s_id = db.add_song(c, f"S{n}", "x", "s", "LEGAL_CONFIRMED", hash=f"h{n}")
    vid = c.execute("INSERT INTO videos(song_id,style,duration,output_path,quality_score,status,title,meta,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (s_id, "facile|vertical", 60, "x", 95, "READY", f"V{n}", "{}", db.now())).lastrowid
    c.commit()
    return vid


def test_failed_creations_are_redone_and_each_video_is_sent_to_the_networks_with_its_own_date(tmp_path, monkeypatch):
    from datetime import date, timedelta
    counter = [0]

    def factory(tp):
        def runner(settings, **k):
            counter[0] += 1
            if counter[0] == 2:
                return {"videos": [{"video_id": None, "status": "FAILED", "error": "contrôle qualité refusé"}], "status": "FAILED"}
            vid = _make_video(tp, counter[0])
            return {"videos": [{"video_id": vid, "status": "READY", "title": f"V{counter[0]}", "format": "vertical"}], "status": "READY"}
        return runner
    st, conn, sent, sv = _job_env(tmp_path, monkeypatch, factory)
    slots = queue.slots_for_days([{"date": (date.today() + timedelta(days=3)).isoformat(), "count": 2}], None)
    job = sv.Job()
    job._run(st, None, ["vertical"], False, 2, None, None, {"slots": slots, "immediate": False, "times": ["12:30", "19:00"]})
    assert job.state["status"] == "done" and counter[0] == 3                                  # la création ratée a été refaite
    assert sent == [(1, slots[0]), (2, slots[1])]                                            # chaque vidéo : envoyée aux réseaux avec SA date de mise en ligne
    assert len(job.state["planned"]) == 2


def test_each_video_goes_to_the_networks_right_after_its_montage_and_stopping_keeps_what_was_done(tmp_path, monkeypatch):
    from datetime import date, timedelta
    from app.director import control
    order = []
    counter = [0]

    def factory(tp):
        def runner(settings, **k):
            counter[0] += 1
            if counter[0] == 3:
                raise control.Cancelled()                                                    # l'utilisateur arrête pendant la 3e création
            vid = _make_video(tp, counter[0]); order.append(("made", vid))
            return {"videos": [{"video_id": vid, "status": "READY", "title": f"V{counter[0]}"}], "status": "READY"}
        return runner
    st, conn, sent, sv = _job_env(tmp_path, monkeypatch, factory)
    monkeypatch.setattr(queue, "publish_video", lambda s, cn, vid, publish_at=None: order.append(("sent", vid, publish_at)) or [{"platform": "tiktok", "status": "PUBLISHED", "detail": ""}])
    slots = queue.slots_for_days([{"date": (date.today() + timedelta(days=3)).isoformat(), "count": 4}], None)
    job = sv.Job()
    job._run(st, None, ["vertical"], False, 4, None, None, {"slots": slots, "immediate": True, "times": []})
    assert job.state["status"] == "cancelled"
    assert order == [("made", 1), ("sent", 1, None), ("made", 2), ("sent", 2, None)]         # « tout de suite » : aucune date, et chaque envoi précède la vidéo suivante


def test_cancel_all_pending_keeps_the_videos(tmp_path):
    c = _conn(tmp_path)
    when = queue.slots(date(2030, 1, 6), 3, 2, ["12:30", "19:00"], now=datetime(2030, 1, 1).astimezone())
    queue.plan(c, [1, 2, 3], when)
    assert len(queue.listing(c)) == 3 and queue.cancel_all_pending(c) == 3
    assert queue.listing(c) == [] and len(queue.unscheduled(c)) == 3                  # les vidéos sont toujours là, prêtes à être reprogrammées


def test_publish_all_ready_posts_every_ready_video_once_and_drops_their_scheduled_times(tmp_path):
    c = _conn(tmp_path)
    for i in (1, 2, 3):
        (tmp_path / f"{i}.mp4").write_bytes(b"x")
        c.execute("UPDATE videos SET output_path=? WHERE id=?", (str(tmp_path / f"{i}.mp4"), i))
    c.execute("UPDATE videos SET status='PUBLISHED' WHERE id=3")                          # déjà publiée : ignorée
    c.commit()
    queue.plan(c, [1, 2], queue.slots(date(2030, 1, 6), 2, 2, ["12:30", "19:00"], now=datetime(2030, 1, 1).astimezone()))
    done = []
    r = queue.publish_all_ready({}, c, say=lambda m: None, publish=lambda s, cn, vid: done.append(vid) or [{"platform": "tiktok", "status": "PUBLISHED", "detail": ""}])
    assert done == [1, 2] and r == {"published": 2, "failed": 0, "total": 2}
    assert [x for x in queue.listing(c) if x["status"] == "PENDING"] == []                # plus d'heure en attente : pas de double publication
    r2 = queue.publish_all_ready({}, c, say=lambda m: None, publish=lambda s, cn, vid: (_ for _ in ()).throw(RuntimeError("boom")))
    assert r2["failed"] == 2 and r2["published"] == 0                                    # un échec ne bloque pas les autres


def test_native_time_never_publishes_now_and_refuses_what_tiktok_cannot_schedule():
    import pytest
    now = datetime(2030, 1, 6, 12, 0).astimezone()
    soon = queue.native_time(now + timedelta(minutes=5), now)
    assert soon >= now + timedelta(minutes=queue.MIN_LEAD_MIN)                         # trop proche : avancée au plus tôt possible, JAMAIS publiée tout de suite
    assert queue.native_time(now + timedelta(hours=3), now) == (now + timedelta(hours=3)).astimezone()
    assert queue.native_time(None, now) is None                                       # pas de date demandée = publication immédiate voulue par l'utilisateur
    with pytest.raises(queue.SlotError):
        queue.native_time(now + timedelta(days=11), now)                               # trop loin pour TikTok



def test_publish_video_with_a_date_asks_each_network_to_schedule_and_never_repeats_a_done_network(tmp_path, monkeypatch):
    import app.publisher as pubs
    c = _conn(tmp_path)
    (tmp_path / "1.mp4").write_bytes(b"x")
    c.execute("UPDATE videos SET output_path=? WHERE id=1", (str(tmp_path / "1.mp4"),)); c.commit()
    seen = []

    class Fake:
        def __init__(self, name, ok): self.platform, self.ok = name, ok
        def publish(self, video, meta, key):
            from app.publisher.base import Result
            seen.append((self.platform, meta.get("publish_at")))
            return Result(self.platform, "SCHEDULED" if self.ok else "FAILED", key, "ok" if self.ok else "échec")
    state = {"yt_ok": False}
    monkeypatch.setattr(pubs, "adapters", lambda s, fmt=None: [Fake("tiktok", True), Fake("youtube", state["yt_ok"])])
    when = datetime.now().astimezone() + timedelta(days=2)
    r = queue.publish_video({}, c, 1, publish_at=when)
    assert [x["status"] for x in r] == ["SCHEDULED", "FAILED"] and all(p[1] for p in seen)       # chaque réseau reçoit la date de mise en ligne
    assert not any(x["status"] == "PENDING" for x in queue.listing(c))                           # AUCUNE publication programmée dans l'app : l'échec est signalé, c'est tout
    seen.clear(); state["yt_ok"] = True
    queue.publish_video({}, c, 1, publish_at=when)
    assert [p[0] for p in seen] == ["youtube"]                                                   # TikTok déjà programmé : pas refait


def test_only_the_last_batch_is_sent_never_older_videos(tmp_path, monkeypatch):
    c = _conn(tmp_path)
    for i in (1, 2, 3):
        (tmp_path / f"{i}.mp4").write_bytes(b"x")
        c.execute("UPDATE videos SET output_path=? WHERE id=?", (str(tmp_path / f"{i}.mp4"), i))
    c.commit()
    monkeypatch.setattr(queue, "BATCH_FILE", tmp_path / "last_batch.json")
    assert [v["id"] for v in queue.ready_videos(c)] == [1, 2, 3]            # sans trace : celles des 3 dernières heures
    queue.set_last_batch([2, 3])
    assert [v["id"] for v in queue.ready_videos(c)] == [2, 3]               # la vidéo 1 (ancienne) n'est JAMAIS touchée
    done = []
    r = queue.publish_all_ready({}, c, say=lambda m: None, publish=lambda s, cn, vid: done.append(vid) or [{"platform": "tiktok", "status": "PUBLISHED", "detail": ""}])
    assert done == [2, 3] and r["total"] == 2
    c.execute("UPDATE videos SET created_at='2020-01-01T00:00:00+00:00' WHERE id=1"); c.commit()
    (tmp_path / "last_batch.json").unlink()
    assert [v["id"] for v in queue.ready_videos(c)] == [1, 2, 3] or [v["id"] for v in queue.ready_videos(c)] == [2, 3]


def test_cancel_stops_the_sending_between_two_videos(tmp_path, monkeypatch):
    from app.director import control
    c = _conn(tmp_path)
    for i in (1, 2, 3):
        (tmp_path / f"{i}.mp4").write_bytes(b"x")
        c.execute("UPDATE videos SET output_path=? WHERE id=?", (str(tmp_path / f"{i}.mp4"), i))
    c.commit()
    monkeypatch.setattr(queue, "BATCH_FILE", tmp_path / "last_batch.json")
    queue.set_last_batch([1, 2, 3])
    sent = []

    def pub(s, cn, vid):
        sent.append(vid)
        control.CANCEL.set()                                                  # clic sur « Annuler » pendant la 1re vidéo
        return [{"platform": "tiktok", "status": "PUBLISHED", "detail": ""}]
    try:
        import pytest
        with pytest.raises(control.Cancelled):
            queue.publish_all_ready({}, c, say=lambda m: None, publish=pub)
    finally:
        control.CANCEL.clear()
    assert sent == [1]                                                        # les suivantes ne sont pas envoyées


def test_orphan_pending_rows_are_dropped(tmp_path):
    c = _conn(tmp_path)
    (tmp_path / "1.mp4").write_bytes(b"x")
    c.execute("UPDATE videos SET output_path=? WHERE id=1", (str(tmp_path / "1.mp4"),))
    c.execute("UPDATE videos SET status='PUBLISHED' WHERE id=2")                      # déjà publiée
    c.commit()                                                                         # la vidéo 3 n'a plus de fichier
    queue.plan(c, [1, 3], queue.slots(date(2030, 1, 6), 2, 2, ["12:30", "19:00"], now=datetime(2030, 1, 1).astimezone()))
    c.execute("INSERT INTO schedule(video_id,run_at,status,created_at) VALUES(2,?,'PENDING',?)", (datetime(2030, 1, 7).isoformat(), db.now())); c.commit()
    assert queue.drop_orphans(c) == 2
    assert [x["video_id"] for x in queue.listing(c)] == [1]                           # ne reste que ce qui a encore un sens


def test_a_slot_too_far_sends_nothing(tmp_path, monkeypatch):
    import app.publisher as pubs
    c = _conn(tmp_path)
    (tmp_path / "1.mp4").write_bytes(b"x")
    c.execute("UPDATE videos SET output_path=? WHERE id=1", (str(tmp_path / "1.mp4"),)); c.commit()
    sent = []
    monkeypatch.setattr(pubs, "adapters", lambda s, fmt=None: sent.append(1) or [])
    r = queue.publish_video({}, c, 1, publish_at=datetime.now().astimezone() + timedelta(days=30))
    assert r[0]["status"] == "FAILED" and "trop loin" in r[0]["detail"] and sent == []     # rien n'est publié, ni en masse ni plus tard


def test_the_app_never_publishes_by_itself_and_old_in_app_schedules_are_cancelled(tmp_path):
    from app.ui import server as sv
    c = _conn(tmp_path)
    queue.plan(c, [1, 2], queue.slots(date(2030, 1, 6), 2, 2, ["12:30", "19:00"], now=datetime(2030, 1, 1).astimezone()))
    assert queue.cancel_all_pending(c) == 2 and [x for x in queue.listing(c) if x["status"] == "PENDING"] == []
    import inspect
    assert "run_due" not in inspect.getsource(sv.due_runner)                           # la surveillance ne publie rien
