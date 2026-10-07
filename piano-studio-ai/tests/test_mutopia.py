import random
from app.music_discovery import mutopia
from tests.helpers import song

# Pages SIMULÉES (le vrai HTML n'a pas pu être vérifié) : elles testent la logique de filtrage des licences.
LIST = '<a href="piece-info.cgi?id=1">a</a><a href="piece-info.cgi?id=2">b</a><a href="piece-info.cgi?id=3">c</a>'
def page(lic, mid=True):
    return f'<html><title>Sonatina | Mutopia</title>Composer: Beethoven <br> Licence: {lic}' + ('<a href="../ftp/x/y.mid">midi</a>' if mid else "") + '</html>'


def test_parse_accepts_only_free_licenses():
    assert mutopia.parse_piece(page("Public Domain"), mutopia.BASE + "cgibin/p")["license"] == "Public Domain"
    assert mutopia.parse_piece(page("Creative Commons Attribution 4.0"), mutopia.BASE + "cgibin/p")["credit"]
    assert mutopia.parse_piece(page("Creative Commons Attribution-ShareAlike 4.0"), "u") is None
    assert mutopia.parse_piece(page("Creative Commons Attribution-NonCommercial"), "u") is None
    assert mutopia.parse_piece(page("All rights reserved"), "u") is None
    assert mutopia.parse_piece(page("Public Domain", mid=False), "u") is None


def test_fetch_one_skips_bad_and_returns_valid():
    pages = {"id=1": page("All rights reserved"), "id=2": page("Public Domain"), "id=3": page("Creative Commons Attribution-NonCommercial")}
    def get(url):
        if "make-table" in url: return LIST
        if url.endswith(".mid"): return song()
        return next(v for k, v in pages.items() if k in url)
    info, data = mutopia.fetch_one(get=get, rnd=random.Random(1), debug=lambda *_: None)
    assert info["license"] == "Public Domain" and data[:4] == b"MThd"


def test_offline_falls_back(tmp_path, monkeypatch):
    from app import config
    from app.director import pipeline
    monkeypatch.setattr(mutopia, "fetch_one", lambda **k: (_ for _ in ()).throw(OSError("offline")))
    s = config.load_settings()
    s["paths"] = {**s["paths"], "data_dir": str(tmp_path), "database": str(tmp_path / "d.sqlite3")}
    r = pipeline.run_one(s, seed=2, dry_run=True)
    assert r["status"] == "DRY_RUN"


def test_title_and_composer_are_cleaned():
    html_ = '<html><title>Consolation, S.172 No.1, by F. Liszt (1811–1886) | Mutopia</title>Licence: Public Domain<a href="a.mid">m</a></html>'
    info = mutopia.parse_piece(html_, mutopia.BASE + "cgibin/p")
    assert info["title"] == "Consolation, S.172 No.1" and info["composer"] == "F. Liszt"
