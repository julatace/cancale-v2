from datetime import datetime, timedelta, timezone

from app import config
from app.database import db
from app.scheduler import autopilot, queue as squeue


def _conn(tmp_path):
    return db.connect(tmp_path / "t.db")


def _now():
    return datetime(2026, 10, 12, 8, 0).astimezone()


def _add_done(conn, when):
    conn.execute("INSERT INTO schedule(video_id,run_at,status,created_at) VALUES(?,?,'DONE','n')", (None, squeue._utc(when)))
    conn.commit()


def test_deficit_counts_only_missing(tmp_path):
    s = {**config.load_settings(), "autopilot": {"enabled": True, "per_day": 2, "days": 3, "times": "12:30, 19:00"}}
    conn = _conn(tmp_path)
    now = _now()
    tomorrow = (now + timedelta(days=1)).replace(hour=12, minute=30)
    _add_done(conn, tomorrow)
    d = {x["date"]: x["count"] for x in autopilot.deficit(s, conn, now.astimezone(timezone.utc))}
    day0, day1, day2 = [(now + timedelta(days=i)).date().isoformat() for i in range(3)]
    assert d == {day0: 2, day1: 1, day2: 2}


def test_complete_agenda_needs_nothing(tmp_path):
    s = {**config.load_settings(), "autopilot": {"enabled": True, "per_day": 1, "days": 2, "times": "12:30"}}
    conn = _conn(tmp_path)
    now = _now()
    for i in range(2):
        _add_done(conn, (now + timedelta(days=i)).replace(hour=12, minute=30))
    ap = autopilot.AutoPilot()
    assert ap.decide(s, conn, True, 5, now.astimezone(timezone.utc)) is None and "complet" in ap.message


def test_disabled_and_waiting_for_songs(tmp_path):
    base = config.load_settings()
    conn = _conn(tmp_path)
    ap = autopilot.AutoPilot()
    assert ap.decide({**base, "autopilot": {"enabled": False}}, conn, True, 5) is None
    s = {**base, "autopilot": {"enabled": True, "per_day": 1, "days": 3, "times": "23:50"}}
    assert ap.decide(s, conn, True, 0) is None and "morceaux" in ap.message
    assert ap.decide(s, conn, False, 5) is None                       # une fabrication est déjà en cours


def test_backoff_after_failure_then_reset():
    t = [1000.0]
    ap = autopilot.AutoPilot(clock=lambda: t[0])
    ap.started(); ap.finished(0, True)
    assert ap.next_try == 1000 + 30 * 60
    ap.started(); ap.finished(0, True)
    assert ap.next_try == 1000 + 60 * 60
    ap.started(); ap.finished(3, False)
    assert ap.fails == 0 and ap.next_try == 0.0


def test_autostart_plist(tmp_path):
    import plistlib
    from app.scheduler import launchd
    p = launchd.install_agent(tmp_path / "proj", home=tmp_path)
    d = plistlib.loads(p.read_bytes())
    assert d["RunAtLoad"] and d["KeepAlive"] and d["ProgramArguments"][-2:] == ["ui", "--no-browser"]


def test_autopilot_tick_starts_one_job(tmp_path, monkeypatch):
    from app.ui import server
    s = {**config.load_settings(), "autopilot": {"enabled": True, "per_day": 1, "days": 2, "times": "23:50"}}
    s["paths"] = {**s["paths"], "database": str(tmp_path / "x.db")}
    monkeypatch.setattr(server, "my_songs_waiting", lambda s: 3)
    server.PILOT = autopilot.AutoPilot()
    calls = []
    assert server.autopilot_tick(s, start=lambda *a: calls.append(a) or True)
    plan = calls[0][-1]
    assert calls[0][3] is False and plan["immediate"] is False and plan["slots"]
    assert not server.autopilot_tick(s, start=lambda *a: calls.append(a) or True)    # déjà lancé : pas de seconde fabrication
    assert len(calls) == 1


def test_notify_dedup_and_osascript(monkeypatch):
    import platform
    from app import notify
    notify._SENT.clear()
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    calls = []
    t = [100.0]
    run = lambda cmd, **k: calls.append(cmd)
    assert notify.send("T", 'dit "bonjour"', key="a", run=run, now=lambda: t[0])
    assert not notify.send("T", "x", key="a", run=run, now=lambda: t[0] + 60)        # répétition évitée
    assert notify.send("T", "x", key="a", run=run, now=lambda: t[0] + 7 * 3600)
    assert len(calls) == 2 and '\\"bonjour\\"' in calls[0][-1]


def test_notify_silent_off_mac(monkeypatch):
    import platform
    from app import notify
    notify._SENT.clear()
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    assert not notify.send("T", "x", key="b", run=lambda *a, **k: 1 / 0)
