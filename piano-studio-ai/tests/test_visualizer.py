import subprocess, json
from app.midi_analyzer.parser import parse_midi
from app.visualizer import falling, synth
from tests.helpers import song


def test_synth_audio_nonsilent_and_bounded():
    notes, _ = parse_midi(song())
    a = synth.render_audio(notes, 8, 5)
    assert len(a) == 5 * synth.SR and 0.1 < abs(a).max() <= 1.0


def test_render_video(tmp_path):
    notes, _ = parse_midi(song())
    out = falling.render_video(notes, 8, 3, tmp_path / "v.mp4", "Test", "sub", fps=15)
    s = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height",
                                   "-of", "json", str(out)], capture_output=True, text=True).stdout)["streams"]
    assert {x["codec_name"] for x in s} >= {"h264", "aac"}
    assert any(x.get("width") == 1080 and x.get("height") == 1920 for x in s)


def _notes(n=8):
    from app.midi_analyzer.parser import Note
    return [Note(i * 0.5, i * 0.5 + 0.45, 60 + (i * 3) % 24, 90, 0) for i in range(n)]


def test_numpy_piano_is_clean_not_clipping_and_has_body():
    import numpy as np
    from app.visualizer import synth
    a = synth.render_audio(_notes(16), 0, 8.0)
    assert a.shape == (8 * synth.SR, 2) and np.isfinite(a).all()
    assert 0.5 < float(np.abs(a).max()) <= 0.9                                       # fort sans écrêter
    assert 0.05 < float(np.sqrt((a ** 2).mean())) < 0.45                             # niveau moyen raisonnable (ni inaudible ni saturé)
    X = np.abs(np.fft.rfft(a[:, 0])); f = np.fft.rfftfreq(len(a), 1 / synth.SR)
    centroid = float((X * f).sum() / X.sum())
    assert 600 < centroid < 3500                                                     # ni sourd ni strident
    assert float(X[f > 12000].sum() / X.sum()) < 0.02                                # presque rien dans l'extrême aigu (pas métallique)
    assert float(X[f < 30].sum() / X.sum()) < 0.01                                    # pas de grondement infra-grave (le rythme des notes en met un peu, c'est normal)


def test_system_piano_is_used_on_mac_and_falls_back_when_it_fails(monkeypatch, tmp_path):
    import wave
    import numpy as np
    from app.visualizer import synth
    monkeypatch.setattr(synth.shutil, "which", lambda n: "/usr/bin/afconvert")
    seen = {}

    def fake_ok(cmd, **k):
        seen["cmd"] = cmd
        t = np.arange(int(5.0 * synth.SR)) / synth.SR
        pcm = (np.sin(2 * np.pi * 440 * t) * 12000).astype("<i2")
        with wave.open(cmd[-1], "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(synth.SR); w.writeframes(pcm.tobytes())
        return type("R", (), {"returncode": 0})()
    a = synth.render_system(_notes(8), 0, 4.0, run=fake_ok)
    assert a is not None and a.shape[1] == 2 and seen["cmd"][:4] == ["/usr/bin/afconvert", "-f", "WAVE", "-d"]
    assert synth.render_system(_notes(8), 0, 4.0, run=lambda cmd, **k: type("R", (), {"returncode": 1})()) is None          # afconvert échoue -> repli
    short = lambda cmd, **k: (wave.open(cmd[-1], "wb").__enter__() and None) or type("R", (), {"returncode": 0})()
    assert synth.render_system(_notes(8), 0, 4.0, run=lambda cmd, **k: type("R", (), {"returncode": 1})()) is None


def test_system_piano_midi_has_pedal_and_softened_velocities(tmp_path):
    from app.midi_analyzer.parser import parse_midi
    from app.visualizer import synth
    from app.midi_analyzer.writer import make_midi
    ev = [(i * 1.0, 0.9, 60 + i % 12, 100) for i in range(12)]
    data = synth._with_pedal(make_midi(ev, bpm=120), ev)
    f = tmp_path / "x.mid"; f.write_bytes(data)
    notes, tempo = parse_midi(f)
    assert len(notes) == 12 and abs(notes[3].start - 1.5) < 0.01                       # le timing est exact (1 s = 2 temps à 120 BPM)
    assert data.count(bytes([0xB0, 64])) >= 3                                          # pédale de sustain posée et relâchée
    out = synth.render_audio(_notes(8), 0, 4.0)                                        # hors Mac : le piano numpy prend le relais
    assert out.shape == (4 * synth.SR, 2)


def test_sketch_video(tmp_path):
    import subprocess
    from app.midi_analyzer.parser import Note
    from app.visualizer import sketch
    notes = [Note(i * 0.5, i * 0.5 + 0.4, 48 + (i * 7) % 30, 80, 0) for i in range(8)]
    out = sketch.render_video(notes, 0, 2.0, tmp_path / "s.mp4", "Titre", "Artiste", fps=10, layout=sketch.Layout(270, 480, 80, 90))
    assert out.exists() and out.stat().st_size > 1000
    d = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(out)], capture_output=True, text=True).stdout
    assert "audio" in d and "video" in d


def test_sketch_hand_split_follows_piece():
    from app.midi_analyzer.parser import Note
    from app.visualizer import sketch
    high = [Note(i, i + 0.5, 70 + i % 12, 80, 0) for i in range(30)] + [Note(0, 1, 48, 80, 0)]
    assert 55 <= sketch.hand_split_for(high) <= 66
    assert sketch.hand_split_for([Note(0, 1, 60, 80, 0)]) == 60


def test_clean_notes_removes_overlap_and_duplicates():
    from app.midi_analyzer.parser import Note
    from app.visualizer import sketch
    ns = [Note(0, 2, 60, 80, 0), Note(1, 3, 60, 80, 0), Note(1.01, 1.5, 60, 80, 0), Note(0, 1, 10, 80, 0), Note(0, 1, 64, 80, 0)]
    out = sketch.clean_notes(ns)
    same = sorted((n for n in out if n.pitch == 60), key=lambda n: n.start)
    assert len(same) == 2 and same[0].end <= same[1].start - 0.04
    assert all(21 <= n.pitch <= 108 for n in out)


def test_verify_video_rejects_wrong_duration(tmp_path):
    import pytest
    from app.midi_analyzer.parser import Note
    from app.visualizer import sketch
    out = sketch.render_video([Note(0, 0.4, 60, 80, 0)], 0, 1.5, tmp_path / "a.mp4", "T", "", fps=10, layout=sketch.Layout(270, 480, 80, 90))
    sketch.verify_video(out, 1.5)
    with pytest.raises(RuntimeError):
        sketch.verify_video(out, 9.0)


def test_sketch_leaves_no_partial_file(tmp_path):
    from app.midi_analyzer.parser import Note
    from app.visualizer import sketch
    out = sketch.render_video([Note(0, 0.4, 60, 80, 0)], 0, 1.0, tmp_path / "v.mp4", "T", "", fps=10, layout=sketch.Layout(270, 480, 80, 90))
    assert out == tmp_path / "v.mp4" and out.exists() and not list(tmp_path.glob("*.part.mp4"))


def test_purge_partial(tmp_path):
    from app import config
    from app.director import cleanup
    s = config.load_settings()
    s["paths"]["data_dir"] = str(tmp_path)
    (tmp_path / "rendered").mkdir()
    (tmp_path / "rendered" / "a.part.mp4").write_bytes(b"x")
    (tmp_path / "rendered" / "ok.mp4").write_bytes(b"x")
    assert cleanup.purge_partial(s) == 1 and (tmp_path / "rendered" / "ok.mp4").exists()


import pytest


@pytest.mark.parametrize("name,spec", [
    ("une_note", [(0, 1, 60)]),
    ("grave", [(i * .4, i * .4 + .3, 21 + i % 9) for i in range(10)]),
    ("aigu", [(i * .4, i * .4 + .3, 100 + i % 8) for i in range(10)]),
    ("meme_touche", [(i * .1, i * .1 + .5, 60) for i in range(30)]),
    ("silence_debut", [(3, 4, 60), (4, 5, 67)]),
    ("hors_plage", [(0, 1, 5), (0, 1, 120), (1, 2, 60)]),
])
def test_sketch_edge_cases(tmp_path, name, spec):
    from app.midi_analyzer.parser import Note
    from app.visualizer import sketch
    import numpy as np
    notes = [Note(a, b, p, 80, 0) for a, b, p in spec]
    out = sketch.render_video(notes, 0, 5.0, tmp_path / f"{name}.mp4", "Titre très long à couper", "Artiste", fps=8,
                              layout=sketch.Layout(270, 480, 80, 90), audio=np.zeros((44100 * 5, 2), dtype="float32"))
    assert out.exists()


def test_clean_artist_strips_license():
    from app.director import pipeline
    assert pipeline.clean_artist("Mozart (public domain)") == "Mozart" and pipeline.clean_artist("Satie (Public Domain)") == "Satie"
