"""Capture Synthesia -> vidéo verticale 1080x1920 : bandeau titre, app en gros plan, accroche (début) et appel à l'action (fin)."""
import subprocess
import tempfile
from pathlib import Path

W, H, TOP = 1080, 1920, 270          # bandeau titre de 270 px, app dessous (1080x1650)
_FONT = next((f for f in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Helvetica.ttc",
                          "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf") if Path(f).exists()), None)


def _text(td: Path, name: str, txt: str, size: int, y: int, color="white", enable=None) -> str:
    """drawtext via fichier texte (accents, apostrophes, ':' sans échappement)."""
    f = td / f"{name}.txt"
    f.write_text(txt, encoding="utf-8")
    font = f"fontfile='{_FONT}':" if _FONT else ""
    en = f":enable='{enable}'" if enable else ""
    return (f"drawtext={font}textfile='{f}':fontcolor={color}:fontsize={size}:x=(w-text_w)/2:y={y}"
            f":borderw=2:bordercolor=black@0.6{en}")


def build_filter(td: Path, duration: float, title="", subtitle="", hook="", cta="", crop=None) -> str:
    c = f"crop=iw*{crop[2]:.4f}:ih*{crop[3]:.4f}:iw*{crop[0]:.4f}:ih*{crop[1]:.4f}," if crop else ""
    chain = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=40:5,eq=brightness=-0.3[bg];"
             f"[1:v]{c}scale={W}:{H - TOP}:force_original_aspect_ratio=increase,crop={W}:{H - TOP}[fg];"
             f"[bg][fg]overlay=0:{TOP}[v]")
    texts = []
    if title: texts.append(_text(td, "title", title[:42], 62, 55))
    if subtitle: texts.append(_text(td, "sub", subtitle[:50], 36, 140, "0xBFC5E0"))
    if hook: texts.append(_text(td, "hook", hook[:46], 44, 205, "yellow", "between(t,0,3.5)"))
    if cta: texts.append(_text(td, "cta", cta[:46], 44, 205, "yellow", f"gt(t,{max(duration - 3.5, 0):.1f})"))
    if texts:
        chain += ";[v]" + ",".join(texts) + "[v]"
    return chain


def compose_vertical(capture, audio_wav, out, trim: float, duration: float, title="", subtitle="", hook="", cta="",
                     fps=30, crop=None) -> Path:
    """crop = (x, y, w, h) en fractions de l'image capturée (zone de la fenêtre Synthesia)."""
    with tempfile.TemporaryDirectory() as td:
        chain = build_filter(Path(td), duration, title, subtitle, hook, cta, crop)
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", str(trim), "-t", str(duration), "-i", str(capture),
               "-ss", str(trim), "-t", str(duration), "-i", str(capture), "-i", str(audio_wav),
               "-filter_complex", chain, "-map", "[v]", "-map", "2:a", "-r", str(fps), "-c:v", "libx264", "-preset", "medium",
               "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode or not Path(out).exists():
        raise RuntimeError(f"compose: {r.stderr[-300:]}")
    return Path(out)
