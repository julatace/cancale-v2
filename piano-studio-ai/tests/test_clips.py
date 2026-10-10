import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from app import clips, config
from app.database import db


def _video(path: Path, w=270, h=480, secs=2):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc=size={w}x{h}:rate=10:duration={secs}",
                    "-f", "lavfi", "-i", f"sine=frequency={300 + w}:duration={secs}", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)


@pytest.fixture
def env(tmp_path):
    s = config.load_settings()
    s["paths"] = {**s["paths"], "data_dir": str(tmp_path / "data"), "database": str(tmp_path / "data" / "t.db")}
    s["agent"] = {"kind": "clips"}
    s["clips"] = {"folder": str(tmp_path / "Clips"), "description": "Abonne-toi !", "hashtags": "#fyp #pourtoi"}
    (tmp_path / "Clips").mkdir()
    (tmp_path / "data").mkdir()
    return s, db.connect(tmp_path / "data" / "t.db"), tmp_path / "Clips"


def _age(f):
    old = time.time() - 60
    os.utime(f, (old, old))


def test_title_from_name():
    assert clips.title_from_name("01_mon_super_clip.mp4") == "Mon super clip"
    assert clips.title_from_name("12 - Les billes en folie.MOV") == "Les billes en folie"
    assert clips.title_from_name("x.mp4") == "X"


def test_import_consumes_file_and_builds_content(env):
    s, conn, d = env
    f = d / "03_parcours_de_billes.mp4"
    _video(f)
    (d / "03_parcours_de_billes.txt").write_text("Le parcours de billes ultime\nRegarde jusqu'au bout !\n#billes #asmr #satisfying", encoding="utf-8")
    _age(f)
    out = clips.import_pending(s, conn)
    assert out[0]["status"] == "IMPORTED" and out[0]["title"] == "Le parcours de billes ultime"
    assert not f.exists() and not (d / "03_parcours_de_billes.txt").exists()          # pris en charge : le dossier se vide
    r = conn.execute("SELECT * FROM videos").fetchone()
    meta = json.loads(r["meta"])
    assert r["style"] == "clips|vertical" and Path(r["output_path"]).exists()
    assert meta["description"].startswith("Regarde jusqu'au bout !") and meta["hashtags"] == ["#billes", "#asmr", "#satisfying"] and "#fyp" not in meta["description"] and meta["shorts"] is True
    assert meta["tiktok_caption"].startswith("Le parcours de billes ultime")


def test_duplicates_and_unfinished_copies_are_ignored(env):
    s, conn, d = env
    a, b, c = d / "a.mp4", d / "b.mp4", d / "c.mp4"
    _video(a); _video(b)
    b.write_bytes(a.read_bytes())                                   # même contenu
    _age(a); _age(b)
    _video(c)                                                       # fichier tout neuf : copie peut-être en cours
    out = clips.import_pending(s, conn)
    assert sorted(o["status"] for o in out) == ["DUPLICATE", "IMPORTED"] and c.exists()
    assert conn.execute("SELECT COUNT(*) n FROM videos").fetchone()["n"] == 1
    assert (d / "doublons").is_dir()


def test_unreadable_file_is_set_aside(env):
    s, conn, d = env
    f = d / "cassee.mp4"
    f.write_bytes(b"pas une video" * 100)
    _age(f)
    assert clips.import_pending(s, conn)[0]["status"] == "UNREADABLE" and (d / "ignorées" / "cassee.mp4").exists()


def test_horizontal_is_not_a_short_and_queue_order(env):
    s, conn, d = env
    h, v = d / "paysage.mp4", d / "portrait.mp4"
    _video(h, 480, 270); _video(v, 270, 480)
    _age(h); _age(v)
    clips.import_pending(s, conn)
    rows = conn.execute("SELECT style, meta FROM videos ORDER BY id").fetchall()
    fm = {r["style"]: json.loads(r["meta"]) for r in rows}
    assert fm["clips|horizontal"]["shorts"] is False and fm["clips|vertical"]["shorts"] is True
    assert len(clips.queue_ids(conn)) == 2 and clips.available(s, conn) == 2


def test_published_or_uncertain_are_not_requeued(env):
    s, conn, d = env
    for n in "abc":
        f = d / f"{n}.mp4"
        _video(f, 270 + 2 * (ord(n) - 96), 480)
        _age(f)
    clips.import_pending(s, conn)
    ids = [r["id"] for r in conn.execute("SELECT id FROM videos ORDER BY id")]
    conn.execute("INSERT INTO publications(video_id,platform,status,published_at) VALUES(?,?,?,?)", (ids[0], "tiktok", "SCHEDULED", "n"))
    conn.execute("INSERT INTO publications(video_id,platform,status,published_at) VALUES(?,?,?,?)", (ids[1], "tiktok", "UNCERTAIN", "n"))
    conn.commit()
    assert clips.queue_ids(conn) == [ids[2]]


def test_run_one_returns_pipeline_shaped_result(env):
    s, conn, d = env
    with pytest.raises(RuntimeError):
        clips.run_one(s)
    f = d / "ma_video.mp4"
    _video(f)
    _age(f)
    r = clips.run_one(s)
    assert r["status"] == "READY" and r["video_id"] and r["videos"][0]["format"] == "vertical" and r["title"] == "Ma video"


def test_instances_are_isolated(monkeypatch):
    monkeypatch.setenv("PIANO_INSTANCE", "Clips!")
    s = config.load_settings()
    assert config.instance() == "clips" and s["paths"]["database"] == "data/instances/clips/piano.sqlite3"
    assert str(config.data_root()).endswith("data/instances/clips")
    monkeypatch.delenv("PIANO_INSTANCE")
    assert config.instance() == "" and config.load_settings()["paths"]["database"] == "data/piano.sqlite3"


def test_process_lock_is_exclusive(tmp_path):
    from app.scheduler import queue as q
    lock = tmp_path / "send.lock"
    assert q._proc_lock_acquire(path=lock)
    import fcntl
    other = open(lock, "w")
    with pytest.raises(OSError):
        fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)                 # un 2e agent doit attendre
    q._proc_lock_release()
    fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
    other.close()


def test_instance_plist_and_init(tmp_path, monkeypatch):
    import plistlib
    from app import cli
    from app.scheduler import launchd
    p = launchd.install_agent(tmp_path / "proj", home=tmp_path, instance="clips")
    d = plistlib.loads(p.read_bytes())
    assert d["Label"].endswith(".clips") and d["ProgramArguments"][2:4] == ["--instance", "clips"]
    monkeypatch.setattr(config, "ROOT", tmp_path)
    args = type("A", (), {"name": "Mes Clips", "profile": "Autre", "folder": str(tmp_path / "F"), "port": 0})()
    assert cli.cmd_instance_init({}, args) == 0
    cfg = json.loads((tmp_path / "data" / "instances" / "mesclips" / "local_settings.json").read_text())
    assert cfg["agent"]["kind"] == "clips" and cfg["tiktok"]["chrome_profile"] == "Autre" and cfg["youtube"]["chrome_profile"] == "Autre"
    assert cfg["inbox"]["watch"] == [] and cfg["ui"]["port"] >= 8766 and (tmp_path / "F").is_dir()


def test_files_being_written_are_ignored(env):
    s, conn, d = env
    (d / "clip.mp4.part").write_bytes(b"x" * 100)
    (d / ".cache.mp4").write_bytes(b"x" * 100)
    _age(d / "clip.mp4.part"); _age(d / ".cache.mp4")
    assert clips.pending(s) == [] and clips.import_pending(s, conn) == []


def test_import_file_and_no_double_send(env, tmp_path):
    s, conn, d = env
    f = tmp_path / "ext.mp4"
    _video(f)
    vid = clips.import_file(s, conn, f, title="Mon titre", hashtags=["#a", "#b"])
    assert f.exists()                                                       # l'original n'est pas touché
    assert clips.import_file(s, conn, f) == vid                              # même contenu : même vidéo, jamais un doublon
    assert json.loads(conn.execute("SELECT meta FROM videos WHERE id=?", (vid,)).fetchone()["meta"])["hashtags"] == ["#a", "#b"]
    conn.execute("INSERT INTO publications(video_id,platform,status,published_at) VALUES(?,?,?,?)", (vid, "youtube", "SCHEDULED", "n"))
    conn.commit()
    with pytest.raises(ValueError):
        clips.import_file(s, conn, f)
    with pytest.raises(ValueError):
        clips.import_file(s, conn, tmp_path / "nope.mp4")


def test_post_command_requires_when_and_publishes(env, tmp_path, monkeypatch):
    from app import cli
    from app.scheduler import queue as q
    s, conn, d = env
    f = tmp_path / "v.mp4"
    _video(f)
    A = lambda **k: type("A", (), {"video": str(f), "title": "T", "description": "", "hashtags": "#x", "at": "", "now": False, **k})()
    assert cli.cmd_post(s, A()) == 1                                         # ni --at ni --now : on refuse, rien ne part
    calls = []
    monkeypatch.setattr(q, "publish_video", lambda s_, c_, vid, publish_at=None: calls.append(publish_at) or [{"platform": "tiktok", "status": "SCHEDULED"}, {"platform": "youtube", "status": "SCHEDULED"}])
    assert cli.cmd_post(s, A(at="2030-01-02 19:00")) == 0 and calls[0].year == 2030
    monkeypatch.setattr(q, "publish_video", lambda *a, **k: [{"platform": "tiktok", "status": "FAILED", "detail": "x"}])
    assert cli.cmd_post(s, A(now=True)) == 1
