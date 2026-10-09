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


def test_dense_song_of_mine_raises_the_level_instead_of_being_thrown_away(tmp_path):
    from app.database import db
    from app.director import pipeline
    st = _st(tmp_path)
    st["engine"] = "builtin"
    inbox.set_rights(st, True)
    (inbox.folder(st) / "Gars - Alpha.mid").write_bytes(song(sparse_beats=100, busy_beats=140))
    inbox.scan(st, srv_mod.import_upload)
    r = pipeline.run_one(st, seed=1, publish=False, formats=["vertical"])        # niveau non imposé : rotation -> « Facile », trop lent pour ce morceau
    assert r["song"] == "Alpha" and r["status"] == "READY" and r["difficulty"] != "Facile"


def test_page_endpoints_for_my_folder(tmp_path, monkeypatch):
    import threading, urllib.request, urllib.error
    from http.server import ThreadingHTTPServer
    st = _st(tmp_path)
    mine = tmp_path / "MIDI"; mine.mkdir()
    (mine / "Gars - Alpha.mid").write_bytes(song())
    monkeypatch.setattr(srv_mod.config, "save_local", lambda k, v: st.__setitem__(k, {**st.get(k, {}), **v}))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), srv_mod.make_handler(lambda: st))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"

    def call(path, body=None):
        req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None, headers={"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
        try:
            r = urllib.request.urlopen(req); return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())
    assert call("/api/folder", {"path": str(tmp_path / "nope")})[0] == 400
    code, d = call("/api/folder", {"path": str(mine)})
    assert code == 200 and d["folders"][0]["files"] == 1 and d["waiting"] == 1
    assert call("/api/inbox/scan", {})[0] == 403                           # droits pas encore confirmés
    call("/api/inbox/rights", {"confirmed": True})
    code, r = call("/api/inbox/scan", {})
    assert code == 200 and r["imported"] == 1 and r["to_make"] == 1 and r["waiting"] == 0
    httpd.shutdown()


def test_same_artist_is_not_used_twice_in_a_row_when_there_is_a_choice(tmp_path):
    from app.database import db
    from app.director import pipeline
    st = _st(tmp_path)
    conn = db.connect(tmp_path / "d.sqlite3")
    src = "user_owned: Fourni par l'utilisateur (droits confirmés)"
    ids = {}
    for i, (t, a) in enumerate([("A1", "Bach"), ("A2", "Bach"), ("B1", "Chopin")]):
        f = tmp_path / f"m{i}.mid"; f.write_bytes(song(sparse_beats=16 + i))
        ids[t] = db.add_song(conn, t, a, src, "LEGAL_CONFIRMED", midi_path=f, hash=f"h{i}")
    conn.execute("INSERT INTO videos(song_id,style,duration,output_path,quality_score,status,title,meta,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                 (ids["A1"], "facile|vertical", 60, "x", 95, "PUBLISHED", "t", "{}", db.now()))
    conn.commit()
    assert pipeline.pick_song(conn, st, 1)[2]["title"] == "B1"           # Bach vient de passer : Chopin d'abord, bien que A2 soit arrivé avant


def test_video_export_is_tuned_for_flat_graphics_and_sharpened():
    from app.renderer import compose
    assert "animation" in compose.encode_args(60) and "-tune" in compose.encode_args(60)
    chain, _ = compose.build_filter(__import__("pathlib").Path("/tmp"), 6, "T", "S", "", "", None, (1080, 1920), 460, compose.DEFAULT_BG, (1470, 956))
    assert "unsharp" in chain
