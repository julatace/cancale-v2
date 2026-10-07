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


def test_click_continue_top_right_of_window():
    log = []
    assert mac.start_playback({**CFG, "start_mode": "click"}, fake_run(log)).startswith("click(1044,95)")  # 100+1000-56 ; 50+45
    assert any("click at {1044, 95}" in s for s in log)


def test_return_mode_and_crop_fractions():
    log = []
    assert mac.start_playback({**CFG, "start_mode": "return"}, fake_run(log)) == "return"
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
        mac.start_playback({**CFG, "start_mode": "return"}, run)
