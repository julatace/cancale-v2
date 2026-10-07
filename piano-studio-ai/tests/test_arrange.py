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
