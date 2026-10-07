"""Capture 16:9 de Synthesia -> vidéo verticale 1080x1920 (fond flou + piano pleine largeur) + audio synchronisé."""
import subprocess
from pathlib import Path

_FONT = next((f for f in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf") if Path(f).exists()), None)


def compose_vertical(capture, audio_wav, out, trim: float, duration: float, title="", fps=30) -> Path:
    fg = "[1:v]scale=1080:-2[fg]"
    bg = "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=40:5,eq=brightness=-0.15[bg]"
    chain = f"{bg};{fg};[bg][fg]overlay=(W-w)/2:(H-h)/2[v]"
    if title and _FONT:
        safe = title.replace("\\", "").replace(":", " ").replace("'", "")
        chain += f";[v]drawtext=fontfile='{_FONT}':text='{safe}':fontcolor=white:fontsize=56:x=(w-text_w)/2:y=200[v]"
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", str(trim), "-t", str(duration), "-i", str(capture),
           "-ss", str(trim), "-t", str(duration), "-i", str(capture), "-i", str(audio_wav),
           "-filter_complex", chain, "-map", "[v]", "-map", "2:a", "-r", str(fps), "-c:v", "libx264", "-preset", "medium",
           "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode or not Path(out).exists():
        raise RuntimeError(f"compose: {r.stderr[-300:]}")
    return Path(out)
