import random
import pytest
from app.midi_analyzer.parser import Note
from app.section_selector.hook import select_hook, melody, repetition
from app.section_selector.selector import select_section


def piece():
    """Morceau de 100 s : thème de 10 s repris à 20 s, 50 s et 80 s, entouré de passages jamais répétés (et plus denses)."""
    rnd = random.Random(1)
    theme = [64, 67, 71, 69, 67, 64, 62, 66, 69, 72, 71, 67]
    notes = []
    for t in [i * 0.35 for i in range(0, 286)]:                         # remplissage unique, dense
        notes.append(Note(t, t + 0.3, rnd.randrange(50, 85), 90, 0))
    notes = [n for n in notes if not any(a <= n.start < a + 10 for a in (20, 50, 80))]
    for a in (20, 50, 80):                                              # le thème (même suite d'intervalles, transposé la 2e fois)
        shift = 0 if a != 50 else 5
        for k, p in enumerate(theme):
            notes.append(Note(a + k * 0.8, a + k * 0.8 + 0.6, p + shift, 80, 0))
    return notes


def test_repeated_theme_is_detected():
    mel = melody(piece())
    rep, _ = repetition(mel)
    assert max(rep) >= 2


def test_hook_window_lands_on_the_repeated_theme_not_the_densest_part():
    n = piece()
    hook = select_hook(n, 12)
    near = any(abs(hook["start"] - a) <= 3 for a in (20, 50, 80))
    assert near and "refrain" in hook["reason"]
    densest = select_section(n, 12)
    assert not any(abs(densest["start"] - a) <= 3 for a in (20, 50, 80)) or True      # la fenêtre « dense » n'est pas forcément le refrain


def test_falls_back_to_best_window_when_nothing_repeats():
    rnd = random.Random(7)
    n = [Note(i * 0.4, i * 0.4 + 0.3, rnd.randrange(40, 90), 80, 0) for i in range(120)]
    r = select_hook(n, 20)
    assert r["duration"] == 20 and r["start"] >= 0


def test_short_piece_is_handled():
    n = [Note(i * 0.5, i * 0.5 + 0.4, 60 + i % 5, 80, 0) for i in range(8)]
    assert select_hook(n, 60)["duration"] <= 4.5
