"""FFmpeg : un seul ré-encodage de la capture OBS vers la vidéo finale 9:16."""
import json
import subprocess
from pathlib import Path

SIZES = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}


def load_template(path) -> dict:
    return json.loads(Path(path).read_text())


def build_command(src, dst, tpl: dict, start: float = 0, duration: float | None = None, has_audio=True) -> list[str]:
    w, h = SIZES[tpl["aspect_ratio"]]
    dur = duration or tpl["duration_target"]
    intro, outro = tpl.get("intro_seconds", 0), tpl.get("outro_seconds", 0)
    z = tpl.get("zoom", 1.0)
    vf = [f"scale={int(w * z)}:{int(h * z)}:force_original_aspect_ratio=increase",
          f"crop={w}:{h}", f"fps={tpl['fps']}", "format=yuv420p"]
    if intro: vf.append(f"fade=t=in:st=0:d={intro}")
    if outro: vf.append(f"fade=t=out:st={max(dur - outro, 0)}:d={outro}")
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", str(start), "-t", str(dur),
           "-i", str(src), "-vf", ",".join(vf)]
    if has_audio:
        cmd += ["-af", "loudnorm=I=-16:TP=-1.5:LRA=11"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "18", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart", str(dst)]
    return cmd


def render(src, dst, tpl, start=0, duration=None, retries=3) -> Path:
    has_audio = bool(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(src)],
        capture_output=True, text=True).stdout.strip())
    last = ""
    for _ in range(retries):
        r = subprocess.run(build_command(src, dst, tpl, start, duration, has_audio), capture_output=True, text=True)
        if r.returncode == 0 and Path(dst).exists() and Path(dst).stat().st_size > 0:
            return Path(dst)
        last = r.stderr[-500:]
    raise RuntimeError(f"rendu échoué après {retries} essais: {last}")
