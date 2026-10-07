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
    assert ratio >= 1080 / 1620 * 0.98                                 # toutes les touches jouées + voisines sont gardées
    assert y + h == pytest.approx(content[1] + content[3])            # le bas (clavier) est conservé
    assert w < 0.7                                                      # zoom modéré : on ne voit pas tout le piano
    assert x <= framing.key_x(48) - 0.05 and x + w >= framing.key_x(83) + 0.05   # des touches voisines de chaque côté


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


def test_background_color_is_measured_from_the_capture_and_fills_the_bars(tmp_path):
    import subprocess
    from app.renderer import compose
    cap = tmp_path / "grey.mp4"                     # fausse capture : fond gris (70,70,70) avec une zone claire au centre
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "color=c=0x464646:s=640x480:r=30:d=6,drawbox=x=200:y=150:w=240:h=200:color=white:t=fill",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(cap)], check=True)
    rgb = compose.sample_bg_color(cap, None, at=1.0)
    assert all(abs(c - 70) <= 4 for c in rgb)
    wav = tmp_path / "a.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=300:duration=4", str(wav)], check=True)
    out = compose.compose_vertical(cap, wav, tmp_path / "o.mp4", 0.5, 3, "Titre", "", crop=None, bg=rgb)
    px = subprocess.run(["ffmpeg", "-v", "error", "-ss", "1", "-i", str(out), "-vf", "crop=4:4:20:1840,scale=1:1", "-frames:v", "1",
                         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout    # bas de l'image : barre de fond
    assert all(abs(a - b) <= 6 for a, b in zip(px[:3], rgb)), (px[:3], rgb)


def _fake_synthesia_capture(path, x0=0.30, x1=0.62, progress_bar=True):
    """Fausse capture : fond gris, barre de progression verte FIXE sur toute la largeur en haut, notes vertes qui TOMBENT
    seulement entre x0 et x1, clavier blanc en bas."""
    import subprocess
    W, H = 640, 480
    bx, bw = int(W * x0), int(W * (x1 - x0))
    base = f"color=c=0x3b3b3b:s={W}x{H}:r=10:d=12"
    if progress_bar:
        base += f",drawbox=x=0:y=30:w={W}:h=14:color=0x2ea043:t=fill"           # barre de progression : colorée mais immobile
    graph = (f"{base}[bg];color=c=0x8cf050:s=18x60:r=10:d=12[n1];color=c=0x8cf050:s=18x80:r=10:d=12[n2];color=c=0x8cf050:s=18x40:r=10:d=12[n3];"
             f"[bg][n1]overlay=x={bx}:y='mod(t*90,300)':eval=frame[a];[a][n2]overlay=x={bx + bw - 18}:y='mod(t*110+40,300)':eval=frame[b];"
             f"[b][n3]overlay=x={bx + bw // 2}:y='mod(t*70+90,300)':eval=frame,drawbox=x=0:y=380:w={W}:h=100:color=white:t=fill")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-filter_complex", graph, "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)


def test_played_range_is_measured_from_the_recording_not_assumed(tmp_path):
    cap = tmp_path / "c.mp4"
    _fake_synthesia_capture(cap, 0.30, 0.62)                                              # avec une barre de progression verte pleine largeur
    r = framing.measure_played_range(cap, 0.5, (0, 0, 1, 1), seconds=10, margin=0.0)
    assert r is not None and abs(r[0] - 0.30) < 0.04 and abs(r[1] - 0.62) < 0.05          # la bande réellement utilisée
    wide = framing.measure_played_range(cap, 0.5, (0, 0, 1, 1), seconds=10, margin=0.25)
    assert wide[0] < r[0] and wide[1] > r[1]                                              # des touches voisines sont gardées


def test_nothing_colourful_means_no_measurement(tmp_path):
    import subprocess
    cap = tmp_path / "grey.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=0x3b3b3b:s=320x240:r=10:d=5", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(cap)], check=True)
    assert framing.measure_played_range(cap, 0.0, (0, 0, 1, 1), seconds=4) is None


def test_crop_from_range_keeps_the_whole_measured_band():
    x, y, w, h = framing.crop_from_range((0, 0.06, 1, 0.9), (1470, 956), 0.30, 0.62, 1080 / 1620)
    assert x <= 0.30 and x + w >= 0.62 and y + h == pytest.approx(0.96)


def test_app_is_centred_vertically_and_never_overlaps_the_title():
    from app.renderer import compose
    w, h, y = compose.app_box((1470, 860), None, 1080, 1920, 300)
    assert w == pytest.approx(1080) and abs((y + h / 2) - 960) < 2          # centre de l'app = centre de l'image
    w2, h2, y2 = compose.app_box((600, 1100), None, 1080, 1920, 300)          # app très haute : elle ne passe pas sous le bloc titre
    assert y2 >= 300 and y2 + h2 <= 1920
