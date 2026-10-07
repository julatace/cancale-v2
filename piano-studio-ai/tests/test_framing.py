from types import SimpleNamespace as NS
import pytest
from app import config
from app.midi_analyzer.fold import choose_lowest, fold_notes
from app.midi_analyzer.parser import Note
from app.music_discovery import mutopia
from app.renderer import framing
from app.synthesia_controller import mac


def test_key_positions_are_ordered_and_c4_is_near_the_middle():
    xs = [framing.key_x(p) for p in range(21, 109)]
    assert xs == sorted(xs) and 0 <= xs[0] < 0.03 and 0.97 < xs[-1] <= 1.0
    assert 0.4 < framing.key_x(60) < 0.5


def test_vertical_crop_has_exact_aspect_keeps_keyboard_and_stays_inside():
    content = (0.0, 0.06, 1.0, 0.90)
    x, y, w, h = framing.vertical_crop(content, (1470, 956), 48, 83)
    assert 0 <= x and x + w <= 1.0001 and 0 <= y and y + h <= 1.0001
    ratio = (w * 1470) / (h * 956)
    assert 1080 / 1620 * 0.98 <= ratio <= 0.85                       # au moins le rapport visé : toutes les touches jouées sont gardées
    assert y + h == pytest.approx(content[1] + content[3])            # le bas (clavier) est conservé
    assert w < 0.6                                                      # on a bien zoomé sur la partie jouée


def test_vertical_crop_at_the_edges_never_leaves_the_window():
    for lo in (21, 24, 72):
        x, y, w, h = framing.vertical_crop((0, 0.05, 1, 0.9), (1470, 956), lo, lo + 35)
        assert x >= -1e-9 and x + w <= 1 + 1e-9


def test_adaptive_range_follows_the_music():
    low = [Note(i, i + 1, 40 + i % 12, 80, 0) for i in range(40)]
    high = [Note(i, i + 1, 86 + i % 12, 80, 0) for i in range(40)]
    assert choose_lowest(low, 36) <= 36 and choose_lowest(high, 36) >= 72
    assert all(60 <= n.pitch <= 95 for n in fold_notes(high, 60, 36))


def test_composer_is_read_from_the_mutopia_folder_name():
    f = mutopia._composer_from_path
    assert f("https://www.mutopiaproject.org/ftp/SchumannR/O15/k/k.mid") == "R. Schumann"
    assert f("https://www.mutopiaproject.org/ftp/BachJS/BWV846/p/p.mid") == "J.S. Bach"
    assert f("https://www.mutopiaproject.org/ftp/BeethovenLv/O27/p/p.mid") == "L. Beethoven"
    assert f("https://www.mutopiaproject.org/ftp/Anonymous/x/y.mid") == ""


def test_window_is_maximized_to_the_whole_screen():
    log = []
    def run(cmd, **k):
        s = cmd[-1]; log.append(s)
        if "get bounds" in s: return NS(returncode=0, stdout="0, 0, 1470, 956", stderr="")
        if "position, size" in s: return NS(returncode=0, stdout="0, 40, 1470, 912", stderr="")
        return NS(returncode=0, stdout="", stderr="")
    geo = mac.maximize_window({"window_top_points": 40, "maximize_margin_points": 4}, run, sleep=lambda s: None)
    assert geo[2] == 1470 and any("set size of window 1 to {1470, 912}" in s for s in log)


def test_subtitle_hides_unknown_composer_and_never_shows_level_or_bpm():
    from app.director.pipeline import _subtitle
    assert _subtitle({"artist": "Unknown"}, {"level": "Moyen", "bpm": 100}) == ""
    assert _subtitle({"artist": "J.S. Bach"}, {"level": "Moyen", "bpm": 100}) == "J.S. Bach"
