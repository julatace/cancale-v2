"""Miniature : une vraie image de la vidéo (le moment où il y a le plus de notes à l'écran) avec le titre du morceau en grand."""
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .compose import _font, _wrap


def best_frame(video, duration: float | None = None, samples: int = 10, run=subprocess.run) -> Image.Image:
    """Parmi `samples` images réparties entre 15 % et 85 % de la vidéo, garde la plus colorée (= le plus de notes visibles)."""
    if duration is None:
        r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)], capture_output=True, text=True)
        duration = float(r.stdout.strip() or 10)
    best, best_score = None, -1.0
    for k in range(samples):
        t = duration * (0.15 + 0.70 * k / max(samples - 1, 1))
        r = run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                capture_output=True)
        if not r.stdout:
            continue
        import io
        im = Image.open(io.BytesIO(r.stdout)).convert("RGB")
        a = np.asarray(im.resize((120, 120)), dtype=np.float32)
        score = float(((a.max(axis=2) - a.min(axis=2)) / np.maximum(a.max(axis=2), 1)).mean())     # saturation moyenne
        if score > best_score:
            best, best_score = im, score
    if best is None:
        raise RuntimeError("aucune image extraite de la vidéo")
    return best


def make_thumbnail(video, out, title: str, subtitle: str = "", size: tuple[int, int] | None = None, run=subprocess.run, top_crop: int = 0) -> Path:
    """Crée la miniature JPEG. Format horizontal : 1280x720 (taille YouTube) ; vertical : 1080x1920 (couverture)."""
    frame = best_frame(video, run=run)
    if size is None:
        size = (1280, 720) if frame.width >= frame.height else (1080, 1920)
    W, H = size
    if top_crop > 0:                                       # on retire le bandeau-titre de la vidéo : le titre de la miniature le remplace
        frame = frame.crop((0, min(top_crop, frame.height - 10), frame.width, frame.height))
    scale = max(W / frame.width, H / frame.height)         # remplit la miniature sans déformer, recadrage centré (le bas = clavier gardé)
    fw, fh = int(frame.width * scale + 0.5), int(frame.height * scale + 0.5)
    frame = frame.resize((fw, fh), Image.LANCZOS)
    img = frame.crop(((fw - W) // 2, fh - H, (fw - W) // 2 + W, fh)).convert("RGBA")
    wide = W > H
    band_h = int(H * (0.42 if wide else 0.26))
    grad = Image.new("RGBA", (W, band_h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(band_h):                                  # voile sombre : en bas (horizontal) ou en haut (vertical)
        a = int(215 * ((y / band_h) if wide else (1 - y / band_h)) ** 1.1)
        gd.line([(0, y), (W, y)], fill=(8, 10, 24, a))
    img.alpha_composite(grad, (0, H - band_h if wide else 0))
    d = ImageDraw.Draw(img)
    f, lines = _wrap(d, title, int(H * (0.14 if wide else 0.06)), W - int(W * 0.1), 2)
    block = int(len(lines) * f.size * 1.1) + (int(f.size * 0.6) if subtitle else 0)
    y = (H - block - int(H * 0.06)) if wide else int(H * 0.05)
    for l in lines:
        d.text((W / 2, y), l, font=f, fill=(255, 255, 255, 255), anchor="mt", stroke_width=max(3, f.size // 18), stroke_fill=(0, 0, 0, 230))
        y += int(f.size * 1.1)
    if subtitle:
        d.text((W / 2, y + 6), subtitle, font=_font(int(f.size * 0.5)), fill=(255, 214, 90, 255), anchor="mt", stroke_width=2, stroke_fill=(0, 0, 0, 200))
    out = Path(out)
    img.convert("RGB").save(out, "JPEG", quality=90, optimize=True)
    if out.stat().st_size > 1_900_000:                       # YouTube refuse les miniatures de plus de 2 Mo
        img.convert("RGB").save(out, "JPEG", quality=72, optimize=True)
    return out
