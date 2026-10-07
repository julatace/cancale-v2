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
