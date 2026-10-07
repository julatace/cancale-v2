import json
import pytest
from app import config
from app.music_discovery import search, trends, mutopia
from tests.helpers import song

# Pages SIMULÉES (le vrai HTML de Mutopia n'a pas pu être vérifié depuis le conteneur de développement).
LIST = '<a href="piece-info.cgi?id=11">a</a><a href="piece-info.cgi?id=12">b</a><a href="piece-info.cgi?id=13">c</a>'
def page(title, lic, midi=True):
    return (f'<html><title>{title}, by C. Debussy (1862–1918) | Mutopia</title>Licence: {lic}'
            + ('<a href="../ftp/DebussyC/x/y.mid">midi</a>' if midi else "") + '</html>')
PAGES = {"id=11": page("Clair de lune", "Public Domain"), "id=12": page("Clair de lune (arr.)", "All rights reserved"),
         "id=13": page("Clair de lune (sans midi)", "Public Domain", midi=False)}


def fake_get(url):
    if "make-table" in url: return LIST
    if url.endswith(".mid"): return song()
    return next(v for k, v in PAGES.items() if k in url)


@pytest.fixture
def s(tmp_path):
    st = config.load_settings()
    st["paths"] = {**st["paths"], "data_dir": str(tmp_path / "d"), "database": str(tmp_path / "db.sqlite3"), "logs_dir": str(tmp_path / "l")}
    return st


def test_search_keeps_only_free_licensed_pieces_with_midi(s):
    r = search.search(s, "clair de lune", get=fake_get)
    assert [x["title"] for x in r["results"]] == ["Clair de lune"] and r["results"][0]["license"] == "Public Domain" and not r["message"]


def test_search_says_honestly_when_nothing_free_is_found(s):
    r = search.search(s, "taylor swift", get=lambda u: "<html>aucun résultat</html>")
    assert r["results"] == [] and "protégées par des droits" in r["message"] and "Mes morceaux" in r["message"]


def test_search_offline_is_reported_not_raised(s):
    def boom(u): raise OSError("offline")
    r = search.search(s, "clair de lune", get=boom)
    assert r["results"] == [] and "impossible" in r["message"].lower()


def test_found_piece_is_downloaded_into_the_library_then_found_locally(s):
    r = search.import_found(s, mutopia.BASE + "cgibin/piece-info.cgi?id=11", get=fake_get)
    assert r["status"] == "LEGAL_CONFIRMED" and r["song_id"]
    again = search.search(s, "clair lune", get=lambda u: "<html></html>")        # même hors-ligne, la bibliothèque répond
    assert again["results"] and again["results"][0]["kind"] == "library"


def test_import_refuses_foreign_sites_and_forbidden_licenses(s):
    with pytest.raises(ValueError, match="non autorisée"):
        search.import_found(s, "http://127.0.0.1:8000/secret", get=fake_get)
    with pytest.raises(ValueError, match="licence"):
        search.import_found(s, mutopia.BASE + "cgibin/piece-info.cgi?id=12", get=fake_get)


def test_trends_parse_both_apple_feeds_and_report_failure():
    apple = {"feed": {"results": [{"name": "Song A", "artistName": "Art A"}, {"name": "Song B", "artistName": "Art B"}]}}
    itunes = {"feed": {"entry": [{"im:name": {"label": "Clair de Lune"}, "im:artist": {"label": "Debussy"}}]}}
    assert trends.fetch_trends("fr", get=lambda u: apple)[0] == {"rank": 1, "title": "Song A", "artist": "Art A"}
    t = trends.fetch_trends("fr", "classical", get=lambda u: itunes if "genre=5" in u else {})
    assert t[0]["title"] == "Clair de Lune"
    def boom(u): raise OSError("x")
    with pytest.raises(trends.TrendsUnavailable):
        trends.fetch_trends("us", get=boom)


def test_texts_follow_the_chosen_language():
    from app.content_generator.generate import generate
    en = generate({"title": "Gymnopédie No.1", "artist": "Satie"}, "Facile", 3, set(), 80, "en")
    es = generate({"title": "Gymnopédie No.1", "artist": "Satie"}, "Facile", 3, set(), 80, "es")
    fr = generate({"title": "Gymnopédie No.1", "artist": "Satie"}, "Facile", 3, set(), 80)
    assert "Level" in en["description"] and "easy" in en["description"] and "#foryou" in en["description"] + " #foryou"
    assert "Nivel" in es["description"] and "fácil" in es["description"] and "Niveau" in fr["description"]
    assert en["hook"] != fr["hook"] and en["lang"] == "en"
