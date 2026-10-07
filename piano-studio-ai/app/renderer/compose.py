"""Capture Synthesia -> vidéo verticale 1080x1920 : bandeau titre, app en gros plan, accroche (début) et appel à l'action (fin).
Les textes sont dessinés avec Pillow puis superposés (le ffmpeg de Homebrew n'a pas toujours le filtre `drawtext`)."""
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H, TOP = 1080, 1920, 270          # bandeau titre de 270 px, app dessous (1080x1650)
_FONTS = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Helvetica.ttc",
          "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def _font(size):
    for p in _FONTS:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _line(draw, text, y, size, fill, width=W - 80):
    """Texte centré ; la taille diminue jusqu'à ce qu'il tienne dans la largeur."""
    while size > 22:
        f = _font(size)
        if draw.textlength(text, font=f) <= width:
            break
        size -= 2
    draw.text((W / 2, y), text, font=f, fill=fill, anchor="mt", stroke_width=2, stroke_fill=(0, 0, 0, 170))


def _banner(path: Path, title: str, subtitle: str):
    img = Image.new("RGBA", (W, TOP), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if title: _line(d, title, 45, 62, (255, 255, 255, 255))
    if subtitle: _line(d, subtitle, 130, 38, (191, 197, 224, 255))
    img.save(path)


def _tag(path: Path, text: str):
    img = Image.new("RGBA", (W, 70), (0, 0, 0, 0))
    _line(ImageDraw.Draw(img), text, 8, 44, (255, 220, 40, 255))
    img.save(path)


def build_filter(td: Path, duration: float, title="", subtitle="", hook="", cta="", crop=None) -> tuple[str, list[str]]:
    """Retourne (filtre, entrées PNG supplémentaires)."""
    c = f"crop=iw*{crop[2]:.4f}:ih*{crop[3]:.4f}:iw*{crop[0]:.4f}:ih*{crop[1]:.4f}," if crop else ""
    chain = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=40:5,eq=brightness=-0.3[bg];"
             f"[1:v]{c}scale={W}:{H - TOP}:force_original_aspect_ratio=increase,crop={W}:{H - TOP}[fg];"
             f"[bg][fg]overlay=0:{TOP}[v0]")
    cur, extra, idx = "v0", [], 3          # entrées 0,1 = capture ; 2 = audio ; 3.. = PNG
    layers = []
    if title or subtitle:
        p = td / "banner.png"; _banner(p, title[:60], subtitle[:60]); layers.append((p, 0, ""))
    if hook:
        p = td / "hook.png"; _tag(p, hook[:60]); layers.append((p, 205, ":enable='between(t,0,3.5)'"))
    if cta:
        p = td / "cta.png"; _tag(p, cta[:60]); layers.append((p, 205, f":enable='gt(t,{max(duration - 3.5, 0):.1f})'"))
    for n, (p, y, en) in enumerate(layers):
        out = "v" if n == len(layers) - 1 else f"vl{n}"
        chain += f";[{cur}][{idx}:v]overlay=0:{y}{en}[{out}]"
        cur, idx = out, idx + 1
        extra.append(str(p))
    if not layers:
        chain = chain.replace("[v0]", "[v]")
    return chain, extra


def compose_vertical(capture, audio_wav, out, trim: float, duration: float, title="", subtitle="", hook="", cta="",
                     fps=30, crop=None) -> Path:
    """crop = (x, y, w, h) en fractions de l'image capturée (zone de la fenêtre Synthesia)."""
    with tempfile.TemporaryDirectory() as td:
        chain, pngs = build_filter(Path(td), duration, title, subtitle, hook, cta, crop)
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", str(trim), "-t", str(duration), "-i", str(capture),
               "-ss", str(trim), "-t", str(duration), "-i", str(capture), "-i", str(audio_wav)]
        for p in pngs:
            cmd += ["-i", p]
        cmd += ["-filter_complex", chain, "-map", "[v]", "-map", "2:a", "-r", str(fps), "-c:v", "libx264", "-preset", "medium",
                "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode or not Path(out).exists():
        raise RuntimeError(f"compose: {r.stderr[-300:]}")
    return Path(out)
