from types import SimpleNamespace as NS
from app import config
from app.midi_analyzer.fold import fold_notes
from app.midi_analyzer.parser import parse_midi
from app.music_discovery import generator
from app.synthesia_controller import mac

CFG = config.load_settings()["synthesia"]


def fake_run(log):
    def run(cmd, **k):
        script = cmd[-1] if cmd[0] == "osascript" else ""
        log.append(script)
        if "get bounds" in script: return NS(returncode=0, stdout="0, 0, 1280, 832\n", stderr="")
        if "position, size" in script: return NS(returncode=0, stdout="100, 50, 1000, 700\n", stderr="")
        return NS(returncode=0, stdout="", stderr="")
    return run


def test_fold_into_28_keys():
    notes, _ = parse_midi(generator.compose(3)[0])
    folded = fold_notes(notes, 47, 28)
    assert all(47 <= n.pitch <= 74 for n in folded)
    assert [n.pitch % 12 for n in notes] == [n.pitch % 12 for n in folded]


def test_all_sources_last_at_least_a_minute():
    for name in generator.PD_SONGS:
        n, t = parse_midi(generator.pd_song(name)[0])
        assert max(x.end for x in n) >= 70, name
    for seed in range(5):
        n, _ = parse_midi(generator.compose(seed)[0])
        assert max(x.end for x in n) >= 70, seed


def test_clicks_listen_card_then_continue(monkeypatch):
    log = []
    clicks = []
    monkeypatch.setattr(mac, "click", lambda x, y, run=None: clicks.append((x, y)) or True)
    out = mac.start_playback({**CFG, "start_mode": "click"}, fake_run(log), sleep=lambda s: None)
    k = 1280 / 2000
    assert clicks == [(100 + 1000 - int(88 * k), 50 + int(71 * k))]    # seulement « Continuer » (la carte est déjà sélectionnée)
    assert out.startswith("click")


def test_return_mode_and_crop_fractions():
    log = []
    assert mac.start_playback({**CFG, "start_mode": "return"}, fake_run(log), sleep=lambda s: None) == "return"
    x, y, w, h = mac.crop_fractions(CFG, fake_run([]))
    assert abs(x - 100 / 1280) < 1e-6 and abs(w - 1000 / 1280) < 1e-6 and 0 < y < 1 and 0 < h < 1


def test_accessibility_disabled_is_detected_and_blocks_recording(tmp_path):
    run = lambda cmd, **k: NS(returncode=0, stdout="false", stderr="")
    assert mac.accessibility_ok(run)[0] is False
    import pytest
    with pytest.raises(RuntimeError, match="Accessibilité"):
        mac.record(tmp_path / "a.mid", 5, tmp_path / "o.mp4", CFG, run=run, sleep=lambda s: None)


def test_start_playback_raises_when_not_allowed():
    import pytest
    run = lambda cmd, **k: NS(returncode=1, stdout="0, 0, 1000, 700", stderr="osascript n'est pas autorisé")
    with pytest.raises(RuntimeError):
        mac.start_playback({**CFG, "start_mode": "return"}, run, sleep=lambda s: None)


def test_portrait_window_is_resized_in_9_16_zone():
    log = []
    geo = mac.arrange_window_portrait({**CFG, "portrait_margin_points": 70}, fake_run(log))
    sets = [s for s in log if "set size" in s]
    assert sets and "{" in sets[0]
    h = 832 - 70
    assert f"{{{int(h * 1080 / 1650)}, {h}}}" in sets[0]


def test_content_has_hook_cta_and_platform_captions():
    from app.content_generator.generate import generate
    c = generate({"title": "Für Elise", "artist": "Beethoven"}, "Facile", 4, set())
    assert c["hook"] and c["cta"] and c["tiktok_caption"] and c["instagram_caption"] and "#" in c["description"]


def test_rec_test_reports_black_screen(tmp_path):
    out = tmp_path / "r.mp4"
    def run(cmd, **k):
        if "-list_devices" in cmd:
            return NS(returncode=0, stdout="", stderr="[AVFoundation indev] AVFoundation video devices:\n[AVFoundation indev] [1] Capture screen 0\n[AVFoundation indev] AVFoundation audio devices:\n")
        if "signalstats,metadata=print" in cmd:
            return NS(returncode=0, stdout="", stderr="lavfi.signalstats.YAVG=0.0\nlavfi.signalstats.YAVG=0.0")
        out.write_bytes(b"x" * 5000)
        return NS(returncode=0, stdout="", stderr="")
    ok, msg = mac.rec_test(out, run=run)
    assert not ok and "noire" in msg


def test_rec_test_timeout_explains_permission(tmp_path):
    import subprocess
    def run(cmd, **k):
        if "-list_devices" in cmd:
            return NS(returncode=0, stdout="", stderr="[AVFoundation indev] AVFoundation video devices:\n[AVFoundation indev] [1] Capture screen 0\n[AVFoundation indev] AVFoundation audio devices:\n")
        raise subprocess.TimeoutExpired(cmd, 1)
    ok, msg = mac.rec_test(tmp_path / "r.mp4", run=run)
    assert not ok and "Enregistrement de l'écran" in msg


def test_record_aborts_early_without_screen_permission(tmp_path):
    import pytest, subprocess
    def run(cmd, **k):
        if cmd[0] == "osascript": return NS(returncode=0, stdout="true", stderr="")
        if "-list_devices" in cmd:
            return NS(returncode=0, stdout="", stderr="[AVFoundation indev] AVFoundation video devices:\n[AVFoundation indev] [1] Capture screen 0\n[AVFoundation indev] AVFoundation audio devices:\n")
        raise subprocess.TimeoutExpired(cmd, 1)
    with pytest.raises(RuntimeError, match="Enregistrement d'écran impossible"):
        mac.record(tmp_path / "a.mid", 5, tmp_path / "o.mp4", CFG, run=run, sleep=lambda s: None)


def test_default_backend_is_native_macos_recorder(tmp_path):
    seen = []
    def run(cmd, **k):
        seen.append(cmd[0])
        if cmd[0] == "screencapture":
            (tmp_path / "r.mov").write_bytes(b"x" * 9000)
            return NS(returncode=0, stdout="", stderr="")
        return NS(returncode=0, stdout="", stderr="lavfi.signalstats.YAVG=90.0")
    ok, msg = mac.rec_test(tmp_path / "r.mov", run=run)
    assert ok and seen[0] == "screencapture"
