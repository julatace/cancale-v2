import json
import shutil
import subprocess
import pytest
from app.renderer import render as r
from app import config

pytestmark = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg absent")


def probe(p):
    o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,width,height,duration",
                        "-of", "json", str(p)], capture_output=True, text=True).stdout
    return json.loads(o)["streams"]


def test_render_vertical(tmp_path):
    src = tmp_path / "src.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=30:duration=6",
                    "-f", "lavfi", "-i", "sine=frequency=440:duration=6", "-shortest", "-c:v", "libx264", "-c:a", "aac", str(src)], check=True)
    tpl = r.load_template(config.ROOT / "templates" / "viral.json")
    out = r.render(src, tmp_path / "out.mp4", tpl, start=1, duration=3)
    streams = probe(out)
    v = next(s for s in streams if s["codec_name"] == "h264")
    assert (v["width"], v["height"]) == (1080, 1920)
    assert any(s["codec_name"] == "aac" for s in streams)


def test_render_failure_raises(tmp_path):
    tpl = r.load_template(config.ROOT / "templates" / "clean.json")
    with pytest.raises(RuntimeError):
        r.render(tmp_path / "missing.mp4", tmp_path / "o.mp4", tpl, retries=1)
