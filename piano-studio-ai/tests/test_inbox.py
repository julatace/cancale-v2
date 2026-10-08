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


def test_my_songs_are_used_first_in_arrival_order(tmp_path):
    from app.database import db
    from app.director import pipeline
    st = _st(tmp_path)
    conn = db.connect(tmp_path / "d.sqlite3")
    other = tmp_path / "x.mid"; other.write_bytes(song())
    db.add_song(conn, "Réserve", "Mutopia", "Mutopia: libre", "LEGAL_CONFIRMED", midi_path=other, hash="r")
    for i, n in enumerate(("Premier", "Deuxième")):
        f = tmp_path / f"m{i}.mid"; f.write_bytes(song(sparse_beats=16 + i))
        db.add_song(conn, n, "Moi", "user_owned: Fourni par l'utilisateur (droits confirmés)", "LEGAL_CONFIRMED", midi_path=f, hash=f"m{i}")
    picks = [pipeline.pick_song(conn, st, seed)[2]["title"] for seed in (1, 2, 3)]
    assert picks == ["Premier", "Premier", "Premier"]                       # tant qu'il n'a pas servi, le premier arrivé passe devant
    sid = pipeline.pick_song(conn, st, 1)[0]
    assert pipeline.pick_song(conn, st, 1, exclude={sid})[2]["title"] == "Deuxième"
    assert st["songs"]["prefer_mine"] is True


def test_watched_folder_is_read_without_moving_originals(tmp_path):
    st = _st(tmp_path)
    mine = tmp_path / "Desktop" / "MIDI"; (mine / "sous").mkdir(parents=True)
    (mine / "Gars - A.mid").write_bytes(song()); (mine / "sous" / "Gars - B.kar").write_bytes(song(sparse_beats=20)); (mine / "note.txt").write_text("x")
    st["inbox"] = {"watch": [str(mine)]}
    assert inbox.waiting(st) == 2 and inbox.scan(st, srv_mod.import_upload)[0]["status"] == "WAITING_RIGHTS"
    inbox.set_rights(st, True)
    out = inbox.scan(st, srv_mod.import_upload)
    assert sorted(r["status"] for r in out) == ["LEGAL_CONFIRMED", "LEGAL_CONFIRMED"]
    assert (mine / "Gars - A.mid").exists() and (mine / "sous" / "Gars - B.kar").exists()            # originaux intacts
    assert inbox.waiting(st) == 0 and inbox.scan(st, srv_mod.import_upload) == []                    # jamais relu deux fois
    (mine / "Gars - C.mid").write_bytes(song(sparse_beats=24))
    assert inbox.waiting(st) == 1
