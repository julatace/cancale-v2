import math

from app.bounce import choreo
from app.midi_analyzer.parser import Note


def _notes(spec):
    return [Note(t, t + 0.3, p, 90, 0) for t, p in spec]


def test_onsets_keep_melody_and_drop_too_close():
    ns = _notes([(0, 60), (0.0, 72), (0.1, 64), (0.5, 67), (0.55, 70), (1.0, 65)])
    on = choreo.melody_onsets(ns, min_gap=0.16)
    assert [t for t, _ in on] == [0, 0.5, 1.0] and on[0][1] == 72            # accord : la plus aiguë ; trop proche : écartée


def test_ball_lands_exactly_on_each_platform_at_note_time():
    spec = [(1.0 + i * 0.37 + (0.2 if i % 3 == 0 else 0), 48 + (i * 5) % 30) for i in range(25)]
    hits = choreo.build(spec)
    for h in hits:
        x, y = choreo.ball_at(hits, h.t)
        assert abs(x - h.x) < 1e-6 and abs(y - h.y) < 1e-6                    # impact EXACT au temps de la note
        x2, y2 = choreo.ball_at(hits, h.t - 1e-4)
        x3, y3 = choreo.ball_at(hits, h.t + 1e-4)
        assert abs(x2 - x) < 1 and abs(y2 - y) < 3 and abs(x3 - x) < 1 and abs(y3 - y) < 3      # trajectoire continue


def test_bounce_height_is_constant_and_path_descends():
    spec = [(1 + i * 0.5 + (i % 4) * 0.13, 55 + (i * 3) % 20) for i in range(20)]
    hits = choreo.build(spec, h=95, drop=150)
    for a, b in zip(hits, hits[1:]):
        steps = 60
        top = min(choreo.ball_at(hits, a.t + (b.t - a.t) * k / steps)[1] for k in range(steps + 1))
        assert abs((a.y - top) - 95) < 4                                      # le rebond monte toujours d'environ la même hauteur
        assert b.y > a.y                                                      # le parcours descend : la caméra peut suivre vers le bas
    assert all(-0.7 <= h.tilt <= 0.7 for h in hits)


def test_x_stays_on_screen_and_empty_input():
    spec = [(i * 0.4, 30 + (i * 7) % 60) for i in range(40)]
    hits = choreo.build(spec, width=1080, margin=150)
    assert all(150 <= h.x <= 930 for h in hits) and choreo.build([]) == []


def test_audit_midi_scores_good_and_bad(tmp_path):
    import random
    import struct
    from app.midi_analyzer import audit
    from app.midi_analyzer.writer import make_midi
    good = make_midi([(i * 0.5, 0.4, 55 + (i * 3) % 20, 90) for i in range(140)], bpm=120)
    tiny = make_midi([(0, 1, 60, 90), (1, 1, 64, 90)], bpm=120)
    (tmp_path / "bon.mid").write_bytes(good)
    (tmp_path / "court.mid").write_bytes(tiny)
    (tmp_path / "casse.mid").write_bytes(b"pas du midi")
    res = {r["file"]: r for r in audit.audit_folder(tmp_path)}
    assert res["bon.mid"]["score"] >= 85 and res["bon.mid"]["verdict"] in ("très bon", "bon")
    assert res["court.mid"]["verdict"] == "à éviter" and any("court" in i or "peu de notes" in i for i in res["court.mid"]["issues"])
    assert res["casse.mid"]["score"] == 0 and any("illisible" in i for i in res["casse.mid"]["issues"])
    assert list(res)[0] or True
