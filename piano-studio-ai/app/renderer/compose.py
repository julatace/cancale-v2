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


def _probe_size(path) -> tuple[int, int] | None:
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", str(path)],
                           capture_output=True, text=True, timeout=30)
        w, h = r.stdout.strip().split(",")[:2]
        return int(w), int(h)
    except Exception:
        return None


SAFE_TOP = 150           # TikTok / Shorts masquent le haut (onglets, recherche) : le titre commence plus bas
SAFE_BOTTOM_TALL = 220   # ... et le bas (pseudo, légende, musique) : l'app s'arrête plus haut en vertical


def bottom_for(W: int, H: int) -> int:
    return SAFE_BOTTOM_TALL if H > W else 28


def app_box(src: tuple[int, int] | None, crop, W: int, H: int, top: int, bottom_margin: int | None = None) -> tuple[float, float, float]:
    """(largeur, hauteur, y) de l'app dans la vidéo : la plus grande possible, CENTRÉE verticalement (sans toucher le titre)."""
    bottom_margin = bottom_for(W, H) if bottom_margin is None else bottom_margin
    avail_h = H - top - bottom_margin
    if src:
        cw = (crop[2] if crop else 1.0) * src[0]
        ch = (crop[3] if crop else 1.0) * src[1]
        s = min(W / cw, avail_h / ch)
        w, h = cw * s, ch * s
    else:
        w, h = W, avail_h
    return w, h, max((H - h) / 2, top)


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
    """Coupe le titre en lignes ÉQUILIBRÉES (jamais un mot seul orphelin) ; réduit la police si besoin."""
    raw, words = text.split(), []
    for tok in raw:                                         # « No. 1 », « Op. 15 »... ne se séparent jamais
        if words and words[-1].rstrip(".").lower() in ("no", "op", "nr", "bwv", "k", "s", "hob", "d", "kv") and words[-1].endswith("."):
            words[-1] += " " + tok
        else:
            words.append(tok)
    while size > 34:
        f = _font(size)
        w = lambda s: draw.textlength(s, font=f)
        if w(text) <= width:
            return f, [text]
        if max_lines >= 2 and len(words) >= 2:
            best = min(range(1, len(words)), key=lambda k: max(w(" ".join(words[:k])), w(" ".join(words[k:]))))
            a, b = " ".join(words[:best]), " ".join(words[best:])
            if max(w(a), w(b)) <= width and (len(words) < 4 or len(b.split()) >= 2 or len(a.split()) >= 2):
                return f, [a, b]
        if max_lines >= 3:                                  # 3-4 lignes (panneau latéral) : coupe gloutonne
            lines, cur = [], ""
            for word in words:
                test = (cur + " " + word).strip()
                if w(test) <= width: cur = test
                else: lines.append(cur); cur = word
            lines.append(cur)
            if len(lines) <= max_lines:
                return f, lines
        size -= 4
    return _font(34), [text[:40]]


def _banner(path: Path, title: str, subtitle: str, w: int = W, top: int = TOP, bg=DEFAULT_BG) -> int:
    """Bloc titre dégradé (bleu nuit -> gris de Synthesia) : titre (2 lignes max en vertical), compositeur, centrés dans la hauteur
    disponible. Retourne le bas du texte (pour placer l'accroche juste dessous)."""
    img = Image.new("RGBA", (w, top), (0, 0, 0, 255))
    d = ImageDraw.Draw(img)
    dark = (26, 30, 56)
    for y in range(top):                                  # du bleu nuit en haut jusqu'au gris de Synthesia en bas : continuité du fond
        k = (y / top) ** 0.8
        d.line([(0, y), (w, y)], fill=tuple(int(dark[i] + (bg[i] - dark[i]) * k) for i in range(3)) + (255,))
    tall = top >= 250
    start = 72 if top >= 340 else 78 if tall else 58
    f, lines = _wrap(d, title, start, w - 100, 2 if tall else 1)
    sub_h = ((42 if top >= 340 else 46) if tall else 38) if subtitle else 0
    block = int(len(lines) * f.size * 1.12) + sub_h
    if top >= 340:                                        # vertical : le bloc titre est centré SOUS la zone masquée par TikTok
        y = int(SAFE_TOP + max((top - SAFE_TOP - 96 - block) / 2, 4))      # 96 px sous le texte restent pour la pastille d'accroche
    else:
        y = max(26 if tall else 14, int((top - block) / 2))
    for l in lines:
        d.text((w / 2, y), l, font=f, fill=(255, 255, 255, 255), anchor="mt", stroke_width=2, stroke_fill=(0, 0, 0, 160))
        y += int(f.size * 1.12)
    if subtitle:
        d.text((w / 2, y + (6 if tall else 2)), subtitle, font=_font(38 if top >= 340 else 40 if tall else 30), fill=(200, 206, 235, 255), anchor="mt")
        y += sub_h
    img.save(path)
    return y


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


def build_filter(td: Path, duration: float, title="", subtitle="", hook="", cta="", crop=None, size=(W, H), top=TOP, bg=DEFAULT_BG, src=None) -> tuple[str, list[str]]:
    """Retourne (filtre, entrées PNG supplémentaires)."""
    W, H, TOP = size[0], size[1], top
    c = f"crop=iw*{crop[2]:.4f}:ih*{crop[3]:.4f}:iw*{crop[0]:.4f}:ih*{crop[1]:.4f}," if crop else ""
    chain = (f"color=c={_hex(bg)}:s={W}x{H}:r=30:d={duration:.2f}[bg];"                      # fond = gris de Synthesia
             f"[1:v]{c}scale={W}:{H - TOP - bottom_for(W, H)}:force_original_aspect_ratio=decrease:flags=lanczos[fg];"   # fenêtre entière, jamais rognée
             f"[bg][fg]overlay=(W-w)/2:{int(app_box(src, crop, W, H, TOP)[2])}[v0]")           # app centrée, le gris du fond occupe le reste
    cur, extra, idx = "v0", [], 3          # entrées 0,1 = capture ; 2 = audio ; 3.. = PNG
    layers = []
    _, fh, fy = app_box(src, crop, W, H, TOP)
    ban_h = max(int(fy), TOP)                                           # le bloc titre occupe tout l'espace au-dessus de l'app
    cta_y = int(min(fy + fh + max((H - fy - fh - 84) / 2, 10), H - 96))   # appel à l'abonnement : dans l'espace gris sous l'app
    text_bottom = TOP
    if title or subtitle:
        p = td / "banner.png"; text_bottom = _banner(p, title[:60], subtitle[:60], W, ban_h, bg); layers.append((p, 0, ""))
    pill_y = int(min(max(text_bottom + 28, 10), max(ban_h - 90, 10)))   # accroche : juste sous le texte, sans toucher l'app
    if hook:
        p = td / "hook.png"; _tag(p, hook[:60], W); layers.append((p, pill_y, ":enable='between(t,0,3.5)'"))
    if cta:
        p = td / "cta.png"; _tag(p, cta[:60], W)
        layers.append((p, pill_y if H > W else cta_y, f":enable='gt(t,{max(duration - 3.5, 0):.1f})'"))   # vertical : sous le titre, hors de la zone de légende TikTok
    for n, (p, y, en) in enumerate(layers):
        out = "v" if n == len(layers) - 1 else f"vl{n}"
        chain += f";[{cur}][{idx}:v]overlay=0:{y}{en}[{out}]"
        cur, idx = out, idx + 1
        extra.append(str(p))
    if not layers:
        chain = chain.replace("[v0]", "[v]")
    return chain, extra


def encode_args(duration: float, fps: int = 30) -> list[str]:
    """Réglages d'export pour TikTok / YouTube : H.264 High, débit plafonné, BT.709, 30 i/s constants ; son AAC 48 kHz normalisé à -14 LUFS
    (niveau de la plateforme : ni trop faible, ni écrêté) avec une entrée/sortie en fondu pour éviter les claquements."""
    af = f"loudnorm=I=-14:TP=-1.5:LRA=11,afade=t=in:d=0.04,afade=t=out:st={max(duration - 0.7, 0):.2f}:d=0.7"
    return ["-af", af, "-r", str(fps), "-fps_mode", "cfr", "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-profile:v", "high", "-level", "4.2",
            "-maxrate", "14M", "-bufsize", "28M", "-g", str(fps * 2), "-bf", "2", "-pix_fmt", "yuv420p",
            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-shortest", "-movflags", "+faststart"]


def compose_vertical(capture, audio_wav, out, trim: float, duration: float, title="", subtitle="", hook="", cta="",
                     fps=30, crop=None, size=(W, H), top=TOP, bg=DEFAULT_BG) -> Path:
    """crop = (x, y, w, h) en fractions de l'image capturée (zone de la fenêtre Synthesia)."""
    with tempfile.TemporaryDirectory() as td:
        chain, pngs = build_filter(Path(td), duration, title, subtitle, hook, cta, crop, size, top, bg, _probe_size(capture))
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", str(trim), "-t", str(duration), "-i", str(capture),
               "-ss", str(trim), "-t", str(duration), "-i", str(capture), "-i", str(audio_wav)]
        for p in pngs:
            cmd += ["-i", p]
        cmd += ["-filter_complex", chain, "-map", "[v]", "-map", "2:a"] + encode_args(duration, fps) + [str(out)]
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
        cmd += ["-filter_complex", chain, "-map", "[v]", "-map", "2:a"] + encode_args(duration, fps) + [str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode or not Path(out).exists():
        raise RuntimeError(f"compose: {r.stderr[-300:]}")
    return Path(out)
