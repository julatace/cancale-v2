import pytest
from app.database import db
from app.midi_analyzer.analyzer import analyze
from app.midi_analyzer.parser import MidiError, parse_midi
from app.music_discovery import importer
from app.section_selector.selector import select_section
from tests.helpers import make_midi, song


def test_parse_timing_and_bpm():
    notes, tempo = parse_midi(make_midi([(0, 1, 60, 80), (2, 1, 64, 90)], bpm=120))
    assert tempo[0][1] == pytest.approx(120)
    assert notes[0].start == 0 and notes[0].end == pytest.approx(0.5)
    assert notes[1].start == pytest.approx(1.0)


def test_invalid_midi():
    with pytest.raises(MidiError):
        parse_midi(b"nope")


def test_analyze():
    notes, tempo = parse_midi(song())
    a = analyze(notes, tempo)
    assert a["bpm"] == 120 and a["left_hand_notes"] > 0 and a["right_hand_notes"] > 0


def test_selector_skips_sparse_intro():
    notes, _ = parse_midi(song())  # intro 8s clairsemée, puis dense jusqu'à 24s
    r = select_section(notes, target=10)
    assert r["start"] >= 6 and r["duration"] == 10 and r["score"] > 0 and r["reason"]


def test_selector_short_song_clamps():
    notes, _ = parse_midi(make_midi([(0, 1, 60, 80), (1, 1, 64, 80)]))
    assert select_section(notes, target=45)["duration"] <= 1.0


@pytest.fixture
def conn():
    return db.connect(":memory:")


def test_import_legal_requires_proof(conn, tmp_path):
    f = tmp_path / "a.mid"; f.write_bytes(song())
    r = importer.import_midi(conn, f, "A", "x", "public_domain", None)
    assert r["status"] == "LICENSE_REVIEW"
    assert not db.song_usable(conn, r["song_id"], 30)[0]


def test_import_confirmed_and_duplicate(conn, tmp_path):
    f = tmp_path / "a.mid"; f.write_bytes(song())
    r = importer.import_midi(conn, f, "A", "x", "user_owned", "ma composition", dest_dir=tmp_path / "out")
    assert r["status"] == "LEGAL_CONFIRMED" and db.song_usable(conn, r["song_id"], 30)[0]
    assert importer.import_midi(conn, f, "A", "x", "user_owned", "ma composition")["status"] == "DUPLICATE"


def test_unknown_source_and_garbage(conn, tmp_path):
    f = tmp_path / "a.mid"; f.write_bytes(song())
    assert importer.import_midi(conn, f, "A", "x", "random_site", "trust me")["status"] == "UNKNOWN"
    g = tmp_path / "g.mid"; g.write_bytes(b"garbage")
    assert importer.import_midi(conn, g, "G", "x", "user_owned", "p")["status"] == "REJECTED"


def test_candidate_score():
    w = {"trend": .3, "piano": .2, "short_video": .2, "difficulty": .1, "visual": .1, "novelty": .1}
    c = dict(trend=100, piano=100, short_video=100, difficulty=100, visual=100, novelty=100)
    assert importer.candidate_score(c, w) == 100 and importer.candidate_score(c, w, 15) == 85
