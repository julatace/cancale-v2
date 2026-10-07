import pytest
from app.database import db


@pytest.fixture
def conn():
    return db.connect(":memory:")


def test_only_legal_confirmed_is_usable(conn):
    for lic in ("UNKNOWN", "LICENSE_REVIEW", "REJECTED"):
        sid = db.add_song(conn, "x", "y", "src", lic)
        ok, why = db.song_usable(conn, sid, 30)
        assert not ok and "SKIP SONG" in why
    sid = db.add_song(conn, "ok", "y", "src", "LEGAL_CONFIRMED")
    assert db.song_usable(conn, sid, 30)[0]


def test_invalid_license_rejected(conn):
    with pytest.raises(ValueError):
        db.add_song(conn, "x", "y", "s", "MAYBE")


def test_cooldown_blocks_reuse(conn):
    sid = db.add_song(conn, "ok", "y", "src", "LEGAL_CONFIRMED")
    conn.execute("INSERT INTO videos(song_id,status,created_at) VALUES(?,?,?)", (sid, "READY", db.now()))
    assert not db.song_usable(conn, sid, 30)[0]
    assert db.song_usable(conn, sid, 0)[0]


def test_duplicate_midi_hash_refused(conn):
    db.add_song(conn, "a", "b", "s", "LEGAL_CONFIRMED", hash="h1")
    with pytest.raises(Exception):
        db.add_song(conn, "c", "d", "s", "LEGAL_CONFIRMED", hash="h1")


def test_no_double_publication(conn):
    sid = db.add_song(conn, "a", "b", "s", "LEGAL_CONFIRMED")
    vid = conn.execute("INSERT INTO videos(song_id,status,created_at) VALUES(?,?,?)", (sid, "READY", db.now())).lastrowid
    conn.execute("INSERT INTO publications(video_id,platform,status) VALUES(?,?,?)", (vid, "tiktok", "OK"))
    with pytest.raises(Exception):
        conn.execute("INSERT INTO publications(video_id,platform,status) VALUES(?,?,?)", (vid, "tiktok", "OK"))
