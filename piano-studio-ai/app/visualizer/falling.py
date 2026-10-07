"""Rendu 'notes qui tombent' sans Synthesia ni OBS : frames numpy -> FFmpeg."""
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import synth

W, H = 1080, 1920
KB_H = 340                 # hauteur du clavier
FALL_H = H - KB_H - 330    # zone de chute (330 px en haut pour le titre)
TOP = 330
LOOKAHEAD = 3.0
LEFT, RIGHT = (64, 156, 255), (255, 150, 60)
_BLACK = {1, 3, 6, 8, 10}
_FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/System/Library/Fonts/Helvetica.ttc"]


def _font(size):
    for p in _FONTS:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def key_layout(lo: int, hi: int):
    """x/largeur de chaque pitch entre lo et hi (inclus), touches blanches contiguës."""
    whites = [p for p in range(lo, hi + 1) if p % 12 not in _BLACK]
    ww = W / len(whites)
    pos, idx = {}, {p: i for i, p in enumerate(whites)}
    for p in range(lo, hi + 1):
        if p % 12 in _BLACK:
            left = idx.get(p - 1)
            x = (left + 1) * ww - ww * 0.3 if left is not None else 0
            pos[p] = (x, ww * 0.6, True)
        else:
            pos[p] = (idx[p] * ww, ww, False)
    return pos


def _background(pos, title, subtitle):
    img = Image.new("RGB", (W, H))
    arr = np.zeros((H, W, 3), dtype=np.uint8)
    g = np.linspace(0, 1, H)[:, None]
    arr[..., 0] = (14 + 14 * g).astype(np.uint8); arr[..., 1] = (12 + 10 * g).astype(np.uint8); arr[..., 2] = (28 + 30 * g).astype(np.uint8)
    img = Image.fromarray(arr)
    d = ImageDraw.Draw(img)
    for p, (x, w, blk) in pos.items():
        if not blk:
            d.rectangle([x + 1, H - KB_H, x + w - 1, H], fill=(240, 240, 245))
    for p, (x, w, blk) in pos.items():
        if blk:
            d.rectangle([x, H - KB_H, x + w, H - KB_H * 0.4], fill=(25, 25, 30))
    d.rectangle([0, H - KB_H - 6, W, H - KB_H], fill=(220, 40, 60))
    d.text((W / 2, 130), title, font=_font(64), fill=(255, 255, 255), anchor="mm")
    if subtitle:
        d.text((W / 2, 215), subtitle, font=_font(40), fill=(180, 185, 210), anchor="mm")
    return np.asarray(img).copy()


def render_video(notes, start: float, duration: float, out_path, title="", subtitle="", fps=30, hand_split=60):
    ns = [n for n in notes if n.end > start and n.start < start + duration]
    if not ns:
        raise ValueError("aucune note dans la section")
    lo = max(min(n.pitch for n in ns) - 2, 21); hi = min(max(n.pitch for n in ns) + 2, 108)
    while lo % 12 in _BLACK: lo -= 1
    while hi % 12 in _BLACK: hi += 1
    if hi - lo < 36:
        c = (lo + hi) // 2; lo, hi = c - 18, c + 18
        while lo % 12 in _BLACK: lo -= 1
        while hi % 12 in _BLACK: hi += 1
    pos = key_layout(lo, hi)
    bg = _background(pos, title, subtitle)
    out_path = Path(out_path)
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "a.wav"
        synth.write_wav(wav, synth.render_audio(ns, start, duration))
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "veryfast",
               "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
               "-movflags", "+faststart", str(out_path)]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for i in range(int(duration * fps)):
                p.stdin.write(_frame(bg, ns, start + i / fps, pos, hand_split).tobytes())
            p.stdin.close()
            err = p.stderr.read().decode()[-400:]
            if p.wait() != 0:
                raise RuntimeError(f"ffmpeg: {err}")
        finally:
            if p.poll() is None:
                p.kill()
    return out_path


def _frame(bg, notes, t, pos, split):
    f = bg.copy()
    for n in notes:
        if n.end < t or n.start > t + LOOKAHEAD:
            continue
        x, w, blk = pos[n.pitch]
        y_bot = TOP + FALL_H - (n.start - t) / LOOKAHEAD * FALL_H
        y_top = TOP + FALL_H - (n.end - t) / LOOKAHEAD * FALL_H
        y0, y1 = int(max(y_top, TOP)), int(min(y_bot, TOP + FALL_H))
        if y1 <= y0:
            continue
        col = LEFT if n.pitch < split else RIGHT
        pad = 3 if not blk else 1
        f[y0:max(y1 - 2, y0 + 1), int(x) + pad:int(x + w) - pad] = col
        if n.start <= t < n.end:  # touche enfoncée
            ky = H - KB_H
            f[ky:H - (int(KB_H * 0.4) if blk else 0) if blk else H, int(x) + 1:int(x + w) - 1] = col
    return f
