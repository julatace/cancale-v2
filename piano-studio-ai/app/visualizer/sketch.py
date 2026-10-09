"""Rendu « dessiné à la main » : grosses barres colorées au trait, clavier crayonné, caméra qui zoome / dézoome sur la zone jouée."""
import math
import random
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from app.director import control
from . import synth
from .falling import HORIZONTAL, VERTICAL, Layout, _font  # noqa

LOOKAHEAD = 2.4
MIN_WHITES, MAX_WHITES = 10, 24          # plus serré = plus zoomé
LEFT = ((92, 214, 210), (35, 150, 150))  # (clair, foncé) main gauche
RIGHT = ((248, 128, 90), (205, 85, 55))  # main droite
INK = (38, 36, 40)
PAPER = (251, 249, 243)
_BLACK = {1, 3, 6, 8, 10}
_NAMES = ["C", "C♯", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B♭", "B"]


def _whites_before(p: int) -> int:
    """Nombre de touches blanches strictement avant la hauteur p (échelle continue du clavier)."""
    o, r = divmod(p, 12)
    return o * 7 + sum(1 for k in range(r) if k not in _BLACK)


def xpos(p: int) -> tuple[float, float, bool]:
    """(position, largeur, noire) en unités de touche blanche."""
    if p % 12 in _BLACK:
        return _whites_before(p) - 0.3, 0.6, True
    return float(_whites_before(p)), 1.0, False


class Camera:
    """Fenêtre [a, b] en touches blanches, lissée : se resserre sur les passages calmes, s'élargit quand ça s'étend."""

    def __init__(self, notes, W: int, H: int):
        self.notes, self.ratio = notes, W / H
        lo = min(xpos(n.pitch)[0] for n in notes); hi = max(xpos(n.pitch)[0] for n in notes) + 1
        self.full = (lo - 1, hi + 1)
        c = (lo + hi) / 2
        self.c, self.w = c, min(max(hi - lo + 2, MIN_WHITES), MAX_WHITES)
        if hi - lo > MAX_WHITES:
            self.c = lo + MAX_WHITES / 2

    def target(self, t: float):
        near = [n for n in self.notes if n.end > t - 0.3 and n.start < t + LOOKAHEAD * 0.7]
        if not near:
            return self.c, self.w
        xs = [xpos(n.pitch)[0] for n in near]
        lo, hi = min(xs) - 1.5, max(xs) + 2.5
        w = min(max(hi - lo, MIN_WHITES), MAX_WHITES, max(self.full[1] - self.full[0], MIN_WHITES))
        return (lo + hi) / 2, w

    def step(self, t: float, dt: float):
        c, w = self.target(t)
        k = 1 - math.exp(-dt * 2.2)                       # lissage : mouvements doux, jamais brusques
        self.c += (c - self.c) * k
        self.w += (w - self.w) * k * 0.8
        lo_lim, hi_lim = self.full
        half = self.w / 2
        self.c = min(max(self.c, lo_lim + half), max(hi_lim - half, lo_lim + half))
        return self.c - half, self.c + half


def _wobble(pts, rnd, amp):
    return [(x + rnd.uniform(-amp, amp), y + rnd.uniform(-amp, amp)) for x, y in pts]


def _edges(pts, rnd, amp, step=70):
    """Contour fermé dont chaque côté est découpé en petits segments tremblés (trait de crayon)."""
    out = []
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        n = max(int(math.hypot(x1 - x0, y1 - y0) / step), 1)
        for k in range(n):
            f = k / n
            out.append((x0 + (x1 - x0) * f + rnd.uniform(-amp, amp), y0 + (y1 - y0) * f + rnd.uniform(-amp, amp)))
    return out


def _stroke(d, pts, width, closed=True):
    seq = list(pts) + ([pts[0]] if closed else [])
    d.line(seq, fill=INK, width=width, joint="curve")


def _bar(d, x0, y0, x1, y1, col, seed, width):
    rnd = random.Random(seed)
    amp = max(width * 0.45, 1.5)
    base = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    quad = _edges(base, rnd, amp)
    d.polygon(quad, fill=col[0])
    sh = x1 - (x1 - x0) * 0.26
    d.polygon([(sh, y0), (x1, y0), (x1, y1), (sh, y1)], fill=col[1])                                               # ombre à droite
    _stroke(d, quad, width)
    _stroke(d, _edges(base, rnd, amp * 1.3), max(width - 3, 2))                                                    # 2e trait : effet crayon


def render_frame(notes, t, cam_range, L: Layout, split=60, pressed=None):
    W, H, TOP, KB_H = L.W, L.H, L.TOP, L.KB_H
    a, b = cam_range
    sx = W / (b - a)
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    fall_bot = H - KB_H
    lw = max(int(sx * 0.09), 4)
    for o in range(0, 11):                                                    # pointillés à chaque Do
        x = (o * 7 - a) * sx
        if 0 <= x <= W:
            for y in range(TOP, int(fall_bot), 36):
                d.line([(x, y), (x, y + 18)], fill=(190, 186, 180), width=3)
    visible = sorted((n for n in notes if n.end >= t and n.start <= t + LOOKAHEAD), key=lambda n: n.start)
    for i, n in enumerate(visible):
        px, pw, blk = xpos(n.pitch)
        x0, x1 = (px - a) * sx + sx * 0.04, (px + pw - a) * sx - sx * 0.04
        if x1 < 0 or x0 > W:
            continue
        y1 = fall_bot - (n.start - t) / LOOKAHEAD * (fall_bot - TOP) - 4
        y0 = fall_bot - (n.end - t) / LOOKAHEAD * (fall_bot - TOP)
        y0, y1 = max(y0, TOP), min(y1, fall_bot)
        if y1 - y0 < 6:
            continue
        col = LEFT if n.pitch < split else RIGHT
        _bar(d, x0, y0, x1, y1, col, hash((n.pitch, round(n.start, 3))) & 0xffff, lw)
        if sx > 34 and y1 - y0 > sx * 0.9:
            name = _NAMES[n.pitch % 12]
            f = _font(int(min(sx * 0.62, 60)))
            d.text(((x0 + x1) / 2 - 2, y1 - sx * 0.18), name, font=f, fill=INK, anchor="ms")
    ky = fall_bot
    on = {n.pitch: (LEFT if n.pitch < split else RIGHT) for n in notes if n.start <= t < n.end}
    first, last = int(math.floor(a)) - 1, int(math.ceil(b)) + 1
    for p in range(0, 128):
        px, pw, blk = xpos(p)
        if blk or px + pw < a - 1 or px > b + 1:
            continue
        x0, x1 = (px - a) * sx, (px + pw - a) * sx
        col = on.get(p)
        d.rectangle([x0, ky, x1, H], fill=col[0] if col else (255, 255, 255))
        d.line([(x0 + 1, ky), (x0 + 1, H)], fill=INK, width=3)
    for p in range(0, 128):
        px, pw, blk = xpos(p)
        if not blk or px + pw < a - 1 or px > b + 1:
            continue
        x0, x1 = (px - a) * sx, (px + pw - a) * sx
        col = on.get(p)
        bh = KB_H * 0.62
        d.rectangle([x0, ky, x1, ky + bh], fill=col[1] if col else (30, 30, 34), outline=INK, width=3)
    d.line([(0, ky), (W, ky)], fill=INK, width=7)
    d.line([(0, H - 3), (W, H - 3)], fill=INK, width=6)
    for p in range(0, 128):                                                    # repères Do3 / Do4…
        if p % 12 == 0:
            px = xpos(p)[0]
            if a <= px < b and sx > 30:
                d.text(((px - a) * sx + sx * 0.5, H - 28), f"C{p // 12 - 1}", font=_font(int(min(sx * 0.4, 34))), fill=(120, 118, 124), anchor="ms")
    return img


def _title(img, title, subtitle, L: Layout):
    d = ImageDraw.Draw(img)
    wide = L.W > L.H
    y = 54 if wide else int(L.TOP * 0.45)
    d.text((L.W / 2, y), title, font=_font(46 if wide else 56), fill=INK, anchor="mm")
    if subtitle:
        d.text((L.W / 2, y + (50 if wide else 66)), subtitle, font=_font(30 if wide else 36), fill=(110, 108, 114), anchor="mm")


def hand_split_for(notes, default=60) -> int:
    """Point de partage main gauche / droite : suit le morceau (médiane des hauteurs) au lieu d'un Do central fixe."""
    ps = sorted(n.pitch for n in notes)
    if len(ps) < 8:
        return default
    lo, hi = ps[len(ps) // 10], ps[-len(ps) // 10 - 1]
    if hi - lo < 14:                                   # étendue réduite : tout à une main, on garde la répartition par défaut
        return default
    return int(min(max(ps[len(ps) // 2], 55), 66))


def render_video(notes, start: float, duration: float, out_path, title="", subtitle="", fps=30, hand_split=None, layout: Layout = VERTICAL,
                 result: dict | None = None, audio: np.ndarray | None = None):
    ns = [n for n in notes if n.end > start and n.start < start + duration]
    if not ns:
        raise ValueError("aucune note dans la section")
    rel = [type(n)(n.start - start, n.end - start, n.pitch, n.velocity, n.track, n.channel) for n in ns]
    cam = Camera(rel, layout.W, layout.H)
    hand_split = hand_split if hand_split is not None else hand_split_for(rel)
    out_path = Path(out_path)
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "a.wav"
        synth.write_wav(wav, audio if audio is not None else synth.render_audio(ns, start, duration))
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{layout.W}x{layout.H}", "-r", str(fps), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "veryfast",
               "-crf", "18", "-tune", "animation", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest",
               "-movflags", "+faststart", str(out_path)]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            written = 0
            for i in range(int(duration * fps)):
                if i % 15 == 0:
                    control.check()
                    if control.STOP_RECORD.is_set() and written >= int(5 * fps):
                        control.STOP_RECORD.clear()
                        break
                t = i / fps
                img = render_frame(rel, t, cam.step(t, 1 / fps), layout, hand_split)
                _title(img, title, subtitle, layout)
                p.stdin.write(img.tobytes())
                written += 1
            if result is not None:
                result["duration"] = written / fps
            p.stdin.close()
            err = p.stderr.read().decode()[-400:]
            if p.wait() != 0:
                raise RuntimeError(f"ffmpeg: {err}")
        finally:
            if p.poll() is None:
                p.kill()
    return out_path
