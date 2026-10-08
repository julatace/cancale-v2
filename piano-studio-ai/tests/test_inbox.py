import json

from app import config
from app.music_discovery import inbox
from app.ui import server as srv_mod
from tests.helpers import song


def _st(tmp_path):
    st = config.load_settings()
    st["paths"] = {**st["paths"], "data_dir": str(tmp_path), "database": str(tmp_path / "d.sqlite3"), "logs_dir": str(tmp_path / "l")}
    return st


def test_nothing_is_imported_until_rights_are_confirmed(tmp_path):
    st = _st(tmp_path)
    (inbox.folder(st) / "Gars - Chanson.mid").write_bytes(song())
    assert inbox.scan(st, srv_mod.import_upload)[0]["status"] == "WAITING_RIGHTS"
    assert srv_mod.songs(st) == [] and len(inbox.pending(st)) == 1                  # le fichier reste là, intact
    inbox.set_rights(st, True)
    r = inbox.scan(st, srv_mod.import_upload)
    assert r[0]["status"] == "LEGAL_CONFIRMED" and inbox.pending(st) == []
    assert (inbox.folder(st) / "done" / "Gars - Chanson.mid").exists()
    s = srv_mod.songs(st)
    assert s[0]["title"] == "Chanson" and s[0]["artist"] == "Gars"


def test_sidecar_json_gives_title_and_artist_and_bad_files_are_rejected(tmp_path):
    st = _st(tmp_path)
    inbox.set_rights(st, True)
    d = inbox.folder(st)
    (d / "x1.mid").write_bytes(song()); (d / "x1.json").write_text(json.dumps({"title": "Mon titre", "artist": "Moi"}))
    (d / "cassé.mid").write_bytes(b"pas du midi")
    out = {r["file"]: r["status"] for r in inbox.scan(st, srv_mod.import_upload)}
    assert out["x1.mid"] == "LEGAL_CONFIRMED" and out["cassé.mid"] != "LEGAL_CONFIRMED"
    assert (d / "rejected" / "cassé.mid").exists() and (d / "done" / "x1.json").exists()
    assert srv_mod.songs(st)[0]["title"] == "Mon titre"


def test_duplicate_is_filed_as_done(tmp_path):
    st = _st(tmp_path)
    inbox.set_rights(st, True)
    for n in ("a.mid", "b.mid"):
        (inbox.folder(st) / n).write_bytes(song())
        r = inbox.scan(st, srv_mod.import_upload)
    assert r[0]["status"] == "DUPLICATE" and (inbox.folder(st) / "done" / "b.mid").exists()
