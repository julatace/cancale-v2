import pytest
from app import config
from app.midi_analyzer.arrange import arrange_for_piano, pick_tracks
from app.midi_analyzer.parser import parse_midi, parse_midi_info
from app.ui import server
from tests.helpers import make_band_smf, song


def test_percussion_channel_is_never_read():
    notes, _ = parse_midi(make_band_smf())
    assert all(n.channel != 9 for n in notes)
    assert not any(n.pitch in (36, 37, 38) and n.track == 5 for n in notes)


def test_lyrics_track_is_the_melody_and_bass_is_kept_but_busy_guitar_is_dropped():
    data = make_band_smf()
    notes, _ = parse_midi(data)
    info = parse_midi_info(data)
    keep = pick_tracks(notes, info)
    names = {info[t]["name"] for t in keep}
    assert "Chant" in names and "Basse" in names and "Guitare" not in names
    dur = max(n.end for n in notes)
    assert len(arrange_for_piano(notes, info)) / dur <= 9.0              # lisible : pas plus de ~9 notes par seconde


def test_simple_files_are_left_alone():
    notes, _ = parse_midi(song())
    assert arrange_for_piano(notes, parse_midi_info(song())) == notes


def test_kar_files_are_accepted_by_the_upload(tmp_path):
    st = config.load_settings()
    st["paths"] = {**st["paths"], "data_dir": str(tmp_path), "database": str(tmp_path / "d.sqlite3"), "logs_dir": str(tmp_path / "l")}
    r = server.import_upload(st, "Mai_tre_Gims_-_Bella.kar", make_band_smf())
    assert r["status"] == "LEGAL_CONFIRMED"
    lst = server.songs(st)
    assert lst[0]["artist"] == "Maître Gims" and lst[0]["title"] == "Bella"       # nom de fichier abîmé réparé
    from app.director import pipeline
    out = pipeline.run_one(st, seed=2, dry_run=True, song_id=r["song_id"], level="difficile")
    assert out["song"] == "Bella" and out["status"] == "DRY_RUN"


def test_page_accepts_kar_files():
    from app.ui.page import PAGE
    assert ".kar" in PAGE


def _notes(pitches, step=0.5, dur=0.4):
    from app.midi_analyzer.parser import Note
    return [Note(i * step, i * step + dur, p, 80, 0) for i, p in enumerate(pitches)]


def test_choose_span_keeps_the_real_range_in_whole_octaves():
    from app.midi_analyzer.fold import choose_span
    lo, n = choose_span(_notes([48 + (i * 7) % 49 for i in range(300)]))             # 4 octaves de notes : on ne les écrase pas dans 3
    assert lo % 12 == 0 and n % 12 == 0 and 48 <= n <= 60 and lo <= 48
    lo2, n2 = choose_span(_notes([60 + (i % 5) for i in range(100)]))                 # morceau étroit : minimum de 3 octaves
    assert n2 == 36 and lo2 % 12 == 0
    lo3, n3 = choose_span(_notes([30 + (i * 5) % 70 for i in range(300)]), max_keys=60)   # trop large : plafonné
    assert n3 == 60


def test_fast_passages_are_slowed_down_to_a_readable_rate():
    from app.director import difficulty
    fast = _notes([60 + i % 7 for i in range(400)], step=0.1, dur=0.09)               # 10 attaques / s
    slow = _notes([60 + i % 7 for i in range(60)], step=0.8, dur=0.7)
    assert difficulty.onset_rate(fast) > 8 and difficulty.onset_rate(slow) < 2
    assert difficulty.comfortable_extra(slow, 3.0) == 1.0
    ex = difficulty.comfortable_extra(fast, 3.0)
    assert 0.3 <= ex < 0.5 or ex == 0.5                                               # ralentissement fort, borné à 50 %
    chords = [type(n)(n.start, n.end, n.pitch + k, 80, 0) for n in _notes([60] * 40, step=0.5) for k in (0, 4, 7)]
    assert difficulty.onset_rate(chords) == difficulty.onset_rate(_notes([60] * 40, step=0.5))     # un accord = une seule attaque


def test_level_config_gets_max_rate_even_with_a_partial_settings_file():
    from app import config
    from app.director import difficulty
    lv = difficulty.config(config.load_settings())["levels"]
    assert lv["facile"]["max_rate"] == 3.0 and lv["facile"]["bpm"] == 80 and "label" in lv["moyen"]
