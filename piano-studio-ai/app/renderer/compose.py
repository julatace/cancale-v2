"""Capture Synthesia -> vidéo verticale 1080x1920 : bandeau titre, app en gros plan, accroche (début) et appel à l'action (fin).
Les textes sont dessinés avec Pillow puis superposés (le ffmpeg de Homebrew n'a pas toujours le filtre `drawtext`)."""
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H, TOP = 1080, 1920, 300          # bandeau titre de 300 px, app dessous (1080x1620)
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


def _wrap(draw, text, size, width=W - 100, max_lines=2):
    """Coupe le titre sur 2 lignes max ; réduit la police si besoin."""
    while size > 34:
        f = _font(size)
        words, lines, cur = text.split(), [], ""
        for w_ in words:
            test = (cur + " " + w_).strip()
            if draw.textlength(test, font=f) <= width: cur = test
            else:
                lines.append(cur); cur = w_
        lines.append(cur)
        if len(lines) <= max_lines and all(draw.textlength(l, font=f) <= width for l in lines):
            return f, lines
        size -= 4
    return _font(34), [text[:40]]


def _banner(path: Path, title: str, subtitle: str):
    """Bandeau dégradé : titre en grand (2 lignes max), compositeur, filet doré."""
    img = Image.new("RGBA", (W, TOP), (0, 0, 0, 255))
    d = ImageDraw.Draw(img)
    for y in range(TOP):
        k = y / TOP
        d.line([(0, y), (W, y)], fill=(int(30 - 18 * k), int(34 - 20 * k), int(70 - 40 * k), 255))
    f, lines = _wrap(d, title, 78)
    y = 26
    for l in lines:
        d.text((W / 2, y), l, font=f, fill=(255, 255, 255, 255), anchor="mt", stroke_width=2, stroke_fill=(0, 0, 0, 160))
        y += int(f.size * 1.12)
    if subtitle:
        d.text((W / 2, y + 6), subtitle, font=_font(40), fill=(200, 206, 235, 255), anchor="mt")
    d.rectangle([0, TOP - 5, W, TOP], fill=(255, 196, 40, 255))
    img.save(path)


def _tag(path: Path, text: str):
    """Accroche / appel à l'action : pastille jaune lisible sur n'importe quel fond."""
    img = Image.new("RGBA", (W, 84), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = _font(46)
    while d.textlength(text, font=f) > W - 120 and f.size > 26:
        f = _font(f.size - 2)
    tw = d.textlength(text, font=f)
    d.rounded_rectangle([(W - tw) / 2 - 28, 6, (W + tw) / 2 + 28, 78], radius=36, fill=(255, 196, 40, 240))
    d.text((W / 2, 42), text, font=f, fill=(20, 20, 30, 255), anchor="mm")
    img.save(path)


def build_filter(td: Path, duration: float, title="", subtitle="", hook="", cta="", crop=None) -> tuple[str, list[str]]:
    """Retourne (filtre, entrées PNG supplémentaires)."""
    c = f"crop=iw*{crop[2]:.4f}:ih*{crop[3]:.4f}:iw*{crop[0]:.4f}:ih*{crop[1]:.4f}," if crop else ""
    chain = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=40:5,eq=brightness=-0.3[bg];"
             f"[1:v]{c}scale={W}:{H - TOP}:force_original_aspect_ratio=decrease:flags=lanczos[fg];"   # fenêtre entière, jamais rognée
             f"[bg][fg]overlay=(W-w)/2:{TOP}+(({H - TOP})-h)/2[v0]")
    cur, extra, idx = "v0", [], 3          # entrées 0,1 = capture ; 2 = audio ; 3.. = PNG
    layers = []
    if title or subtitle:
        p = td / "banner.png"; _banner(p, title[:60], subtitle[:60]); layers.append((p, 0, ""))
    if hook:
        p = td / "hook.png"; _tag(p, hook[:60]); layers.append((p, TOP + 12, ":enable='between(t,0,3.5)'"))
    if cta:
        p = td / "cta.png"; _tag(p, cta[:60]); layers.append((p, TOP + 12, f":enable='gt(t,{max(duration - 3.5, 0):.1f})'"))
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
        cmd += ["-filter_complex", chain, "-map", "[v]", "-map", "2:a", "-r", str(fps), "-c:v", "libx264", "-preset", "slow",
                "-crf", "16", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode or not Path(out).exists():
        raise RuntimeError(f"compose: {r.stderr[-300:]}")
    return Path(out)
