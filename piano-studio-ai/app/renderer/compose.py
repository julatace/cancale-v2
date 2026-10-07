"""Capture Synthesia -> vidéo verticale 1080x1920 : bandeau titre, app en gros plan, accroche (début) et appel à l'action (fin).
Les textes sont dessinés avec Pillow puis superposés (le ffmpeg de Homebrew n'a pas toujours le filtre `drawtext`)."""
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H, TOP = 1080, 1920, 300          # défaut vertical : bandeau 300 px, app dessous (1080x1620)
_FONTS = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Helvetica.ttc",
          "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


DEFAULT_BG = (59, 59, 59)       # gris du fond de Synthesia (repli si la mesure échoue)


def sample_bg_color(capture, crop, at: float = 3.0, run=subprocess.run) -> tuple[int, int, int]:
    """Couleur du fond de Synthesia, mesurée dans l'enregistrement (coin haut-gauche de la zone des notes)."""
    c = f"crop=iw*{crop[2]:.4f}:ih*{crop[3]:.4f}:iw*{crop[0]:.4f}:ih*{crop[1]:.4f}," if crop else ""
    try:
        r = run(["ffmpeg", "-v", "error", "-ss", str(at), "-i", str(capture), "-vf",
                 f"{c}crop=iw*0.05:ih*0.04:iw*0.02:ih*0.04,scale=1:1", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                capture_output=True, timeout=60)
        rgb = tuple(r.stdout[:3])
        if len(rgb) == 3 and max(rgb) <= 110 and min(rgb) >= 8:          # un gris sombre plausible
            return rgb
    except Exception:
        pass
    return DEFAULT_BG


def _hex(rgb) -> str:
    return "0x%02x%02x%02x" % tuple(rgb)


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


def _wrap(draw, text, size, width, max_lines=2):
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


def _banner(path: Path, title: str, subtitle: str, w: int = W, top: int = TOP, bg=DEFAULT_BG):
    """Bandeau dégradé : titre (2 lignes max en vertical, 1 en horizontal), compositeur, filet doré."""
    img = Image.new("RGBA", (w, top), (0, 0, 0, 255))
    d = ImageDraw.Draw(img)
    dark = (26, 30, 56)
    for y in range(top):                                  # du bleu nuit en haut jusqu'au gris de Synthesia en bas : continuité du fond
        k = (y / top) ** 0.8
        d.line([(0, y), (w, y)], fill=tuple(int(dark[i] + (bg[i] - dark[i]) * k) for i in range(3)) + (255,))
    tall = top >= 250
    f, lines = _wrap(d, title, 78 if tall else 58, w - 100, 2 if tall else 1)
    y = 26 if tall else 14
    for l in lines:
        d.text((w / 2, y), l, font=f, fill=(255, 255, 255, 255), anchor="mt", stroke_width=2, stroke_fill=(0, 0, 0, 160))
        y += int(f.size * 1.12)
    if subtitle:
        d.text((w / 2, y + (6 if tall else 2)), subtitle, font=_font(40 if tall else 30), fill=(200, 206, 235, 255), anchor="mt")
    img.save(path)


def _tag(path: Path, text: str, w: int = W):
    """Accroche / appel à l'action : pastille jaune lisible sur n'importe quel fond."""
    img = Image.new("RGBA", (w, 84), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = _font(46)
    while d.textlength(text, font=f) > w - 120 and f.size > 26:
        f = _font(f.size - 2)
    tw = d.textlength(text, font=f)
    d.rounded_rectangle([(w - tw) / 2 - 28, 6, (w + tw) / 2 + 28, 78], radius=36, fill=(255, 196, 40, 240))
    d.text((w / 2, 42), text, font=f, fill=(20, 20, 30, 255), anchor="mm")
    img.save(path)


def build_filter(td: Path, duration: float, title="", subtitle="", hook="", cta="", crop=None, size=(W, H), top=TOP, bg=DEFAULT_BG) -> tuple[str, list[str]]:
    """Retourne (filtre, entrées PNG supplémentaires)."""
    W, H, TOP = size[0], size[1], top
    c = f"crop=iw*{crop[2]:.4f}:ih*{crop[3]:.4f}:iw*{crop[0]:.4f}:ih*{crop[1]:.4f}," if crop else ""
    chain = (f"color=c={_hex(bg)}:s={W}x{H}:r=30:d={duration:.2f}[bg];"                      # fond = gris de Synthesia
             f"[1:v]{c}scale={W}:{H - TOP}:force_original_aspect_ratio=decrease:flags=lanczos[fg];"   # fenêtre entière, jamais rognée
             f"[bg][fg]overlay=(W-w)/2:{TOP}+(({H - TOP})-h)/2[v0]")
    cur, extra, idx = "v0", [], 3          # entrées 0,1 = capture ; 2 = audio ; 3.. = PNG
    layers = []
    if title or subtitle:
        p = td / "banner.png"; _banner(p, title[:60], subtitle[:60], W, TOP, bg); layers.append((p, 0, ""))
    if hook:
        p = td / "hook.png"; _tag(p, hook[:60], W); layers.append((p, TOP + 12, ":enable='between(t,0,3.5)'"))
    if cta:
        p = td / "cta.png"; _tag(p, cta[:60], W); layers.append((p, TOP + 12, f":enable='gt(t,{max(duration - 3.5, 0):.1f})'"))
    for n, (p, y, en) in enumerate(layers):
        out = "v" if n == len(layers) - 1 else f"vl{n}"
        chain += f";[{cur}][{idx}:v]overlay=0:{y}{en}[{out}]"
        cur, idx = out, idx + 1
        extra.append(str(p))
    if not layers:
        chain = chain.replace("[v0]", "[v]")
    return chain, extra


def compose_vertical(capture, audio_wav, out, trim: float, duration: float, title="", subtitle="", hook="", cta="",
                     fps=30, crop=None, size=(W, H), top=TOP, bg=DEFAULT_BG) -> Path:
    """crop = (x, y, w, h) en fractions de l'image capturée (zone de la fenêtre Synthesia)."""
    with tempfile.TemporaryDirectory() as td:
        chain, pngs = build_filter(Path(td), duration, title, subtitle, hook, cta, crop, size, top, bg)
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", str(trim), "-t", str(duration), "-i", str(capture),
               "-ss", str(trim), "-t", str(duration), "-i", str(capture), "-i", str(audio_wav)]
        for p in pngs:
            cmd += ["-i", p]
        cmd += ["-filter_complex", chain, "-map", "[v]", "-map", "2:a", "-r", str(fps), "-c:v", "libx264", "-preset", "medium",
                "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode or not Path(out).exists():
        raise RuntimeError(f"compose: {r.stderr[-300:]}")
    return Path(out)


def _side_png(path: Path, w: int, h: int, title: str, subtitle: str, level: str):
    """Panneau latéral du format horizontal : titre en grand, compositeur, niveau."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for x in range(w):                                  # voile sombre qui s'estompe vers l'application
        a = int(150 * (1 - abs(x - w / 2) / (w / 2)) ** 0.2)
        d.line([(x, 0), (x, h)], fill=(8, 10, 28, max(a, 90)))
    f, lines = _wrap(d, title, 66, w - 70, 4)
    y = h // 2 - int(len(lines) * f.size * 0.62) - 40
    for l in lines:
        d.text((w / 2, y), l, font=f, fill=(255, 255, 255, 255), anchor="mt", stroke_width=2, stroke_fill=(0, 0, 0, 170))
        y += int(f.size * 1.15)
    if subtitle:
        d.text((w / 2, y + 14), subtitle, font=_font(36), fill=(200, 206, 235, 255), anchor="mt")
    if level:
        fl = _font(34)
        tw = d.textlength(level, font=fl)
        d.rounded_rectangle([(w - tw) / 2 - 22, y + 78, (w + tw) / 2 + 22, y + 134], radius=28, fill=(255, 196, 40, 245))
        d.text((w / 2, y + 106), level, font=fl, fill=(20, 20, 30, 255), anchor="mm")
    img.save(path)


def compose_landscape(capture, audio_wav, out, trim: float, duration: float, title="", subtitle="", level="", hook="", cta="",
                      fps=30, crop=None, bg=DEFAULT_BG) -> Path:
    """Format horizontal 1920x1080 tiré du MÊME enregistrement vertical : l'app au centre en plein hauteur, le titre sur les côtés."""
    W_, H_ = 1920, 1080
    fw = 720                                            # largeur de l'app (rapport 2:3 de la zone de montage)
    side = (W_ - fw) // 2
    c = f"crop=iw*{crop[2]:.4f}:ih*{crop[3]:.4f}:iw*{crop[0]:.4f}:ih*{crop[1]:.4f}," if crop else ""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        _side_png(td / "left.png", side, H_, title, subtitle, level)
        layers = [(td / "left.png", 0, 0, "")]
        if hook:
            _tag(td / "hook.png", hook[:60], side); layers.append((td / "hook.png", W_ - side, 150, ":enable='between(t,0,3.5)'"))
        if cta:
            _tag(td / "cta.png", cta[:60], side); layers.append((td / "cta.png", W_ - side, 150, f":enable='gt(t,{max(duration - 3.5, 0):.1f})'"))
        chain = (f"color=c={_hex(bg)}:s={W_}x{H_}:r=30:d={duration:.2f}[bg];"
                 f"[1:v]{c}scale={fw}:{H_}:force_original_aspect_ratio=decrease:flags=lanczos,pad={fw}:{H_}:(ow-iw)/2:(oh-ih)/2:color=black[fg];"
                 f"[bg][fg]overlay={side}:0[v0]")
        cur = "v0"
        for n, (p, x, y, en) in enumerate(layers):
            o = "v" if n == len(layers) - 1 else f"vl{n}"
            chain += f";[{cur}][{3 + n}:v]overlay={x}:{y}{en}[{o}]"
            cur = o
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", str(trim), "-t", str(duration), "-i", str(capture),
               "-ss", str(trim), "-t", str(duration), "-i", str(capture), "-i", str(audio_wav)]
        for p, *_ in layers:
            cmd += ["-i", str(p)]
        cmd += ["-filter_complex", chain, "-map", "[v]", "-map", "2:a", "-r", str(fps), "-c:v", "libx264", "-preset", "medium",
                "-crf", "17", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode or not Path(out).exists():
        raise RuntimeError(f"compose: {r.stderr[-300:]}")
    return Path(out)
