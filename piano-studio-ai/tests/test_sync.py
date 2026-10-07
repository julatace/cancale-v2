import subprocess
from app.synthesia_controller import sync, mac
from app import config


def _video(tmp_path, flash_at):
    v = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"color=c=gray:s=360x600:r=30:d=12,drawbox=x=0:y=480:w=360:h=120:color=white:t=fill:enable='gte(t,{flash_at})'",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(v)], check=True)
    return v


def test_detects_first_key_press_time(tmp_path):
    v = _video(tmp_path, 7.0)               # capture : touche allumée à 7.0 s ; on coupe les 4 premières secondes
    t = sync.detect_first_note(v, None, trim=4.0)
    assert t is not None and abs(t - 3.0) < 0.3


def test_returns_none_when_nothing_happens(tmp_path):
    v = _video(tmp_path, 99)
    assert sync.detect_first_note(v, None, trim=1.0) is None


def test_crop_removes_synthesia_toolbar():
    from types import SimpleNamespace as NS
    def run(cmd, **k):
        s = cmd[-1]
        if "get bounds" in s: return NS(returncode=0, stdout="0, 0, 1000, 800", stderr="")
        return NS(returncode=0, stdout="100, 50, 500, 724", stderr="")
    cfg = {**config.load_settings()["synthesia"], "titlebar_points": 24, "crop_toolbar_fraction": 0.12}
    x, y, w, h = mac.crop_fractions(cfg, run)
    content = 724 - 24
    assert abs(y - (50 + 24 + content * 0.12) / 800) < 1e-6 and abs(h - content * 0.88 / 800) < 1e-6
