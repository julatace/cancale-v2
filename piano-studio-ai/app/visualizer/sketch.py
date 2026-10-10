"""Rendu « dessiné à la main » : grosses barres colorées au trait, clavier crayonné, caméra qui zoome / dézoome sur la zone jouée."""
import math
import os
import threading
import random
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import logging
from functools import lru_cache

from app.director import control, progress
from . import synth
from .falling import HORIZONTAL, VERTICAL, Layout, _font as _font_raw  # noqa

log = logging.getLogger(__name__)
_font = lru_cache(maxsize=64)(_font_raw)

LOOKAHEAD = 3.6                          # on voit la note arriver longtemps à l'avance : le temps de placer les doigts
# vue : (touches blanches visibles min, max). « wide » = vue d'ensemble de loin, jusqu'au clavier entier (52 touches blanches)
VIEWS = {"close": (12, 20), "medium": (17, 28), "wide": (30, 52)}
MIN_WHITES, MAX_WHITES = VIEWS["wide"]
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

    def __init__(self, notes, W: int, H: int, view: str = "wide"):
        self.notes, self.ratio = notes, W / H
        self.minw, self.maxw = VIEWS.get(view, VIEWS["wide"])
        lo = min(xpos(n.pitch)[0] for n in notes); hi = max(xpos(n.pitch)[0] for n in notes) + 1
        self.full = (lo - 1, hi + 1)
        c = (lo + hi) / 2
        self.c, self.w = c, min(max(hi - lo + 2, self.minw), self.maxw)
        if hi - lo > self.maxw:
            self.c = lo + self.maxw / 2
        self.w = min(self.w * 1.45, 56.0)                       # départ très large puis dézoom → zoom sur la zone jouée (mise en scène du début)

    def target(self, t: float):
        """Fenêtre qui couvre les notes des 6 prochaines secondes (on ne bouge pas pour une note isolée)."""
        near = [n for n in self.notes if n.end > t - 0.3 and n.start < t + 6.0]
        if not near:
            return self.c, self.w
        xs = [xpos(n.pitch)[0] for n in near]
        lo, hi = min(xs) - 2, max(xs) + 3
        w = min(max(hi - lo, self.minw), self.maxw, max(self.full[1] - self.full[0], self.minw))
        return (lo + hi) / 2, w

    def step(self, t: float, dt: float):
        if t >= getattr(self, "_next", 0.0):              # le plan de caméra change au plus toutes les 2,5 s : image stable, jamais nerveuse
            self.tc, self.tw = self.target(t)
            self._next = t + 2.5
        k = 1 - math.exp(-dt * 1.1)                       # glissement lent et continu
        self.c += (self.tc - self.c) * k
        self.w += (self.tw - self.w) * k
        lo_lim, hi_lim = self.full
        half = self.w / 2
        if half * 2 >= hi_lim - lo_lim:
            self.c = (lo_lim + hi_lim) / 2
        else:
            self.c = min(max(self.c, lo_lim + half), hi_lim - half)
        return self.c - half, self.c + half


@lru_cache(maxsize=4)
def _paper(W: int, H: int) -> Image.Image:
    """Fond « papier » : crème avec grain fin et légères taches douces (calculé une seule fois par taille)."""
    rng = np.random.default_rng(7)
    base = np.array(PAPER, dtype=np.float32)
    blot = rng.normal(0, 1, (max(H // 64, 2), max(W // 64, 2))).astype(np.float32)
    blot = np.asarray(Image.fromarray(((blot - blot.min()) / (np.ptp(blot) or 1) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC), dtype=np.float32) / 255 - 0.5
    grain = rng.normal(0, 1, (H, W)).astype(np.float32)
    arr = base[None, None, :] + (blot * 7 + grain * 2.2)[:, :, None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def _sketch_line(d, x0, y0, x1, y1, seed, width, step=90, amp=2.2):
    """Trait de crayon : segments légèrement décalés, toujours identiques pour une même touche (pas de scintillement)."""
    rnd = random.Random(seed)
    n = max(int(math.hypot(x1 - x0, y1 - y0) / step), 1)
    pts = [(x0 + (x1 - x0) * k / n + (rnd.uniform(-amp, amp) if 0 < k < n else 0), y0 + (y1 - y0) * k / n + (rnd.uniform(-amp, amp) if 0 < k < n else 0)) for k in range(n + 1)]
    d.line(pts, fill=INK, width=width, joint="curve")


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
    img = _paper(W, H).copy()
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
        y1 = fall_bot - (n.start - t) / LOOKAHEAD * (fall_bot - TOP)             # le bas de la barre touche le clavier EXACTEMENT au début de la note
        y0 = fall_bot - (n.end - t) / LOOKAHEAD * (fall_bot - TOP)
        y0, y1 = max(y0, TOP), min(y1, fall_bot)
        if y1 - y0 < 6:
            continue
        col = LEFT if n.pitch < split else RIGHT
        soon = 0 <= n.start - t < 0.7                                           # prochaine note à jouer : trait plus épais, on la repère d'un coup d'œil
        _bar(d, x0, y0, x1, y1, col, hash((n.pitch, round(n.start, 3))) & 0xffff, lw + (3 if soon else 0))
        if sx > 20 * (W / 1080) and y1 - y0 > sx * 0.9:
            name = _NAMES[n.pitch % 12]
            f = _font(int(min(sx * 0.62, 60)))
            d.text(((x0 + x1) / 2 - 2, y1 - sx * 0.18), name, font=f, fill=INK, anchor="ms")
    ky = fall_bot
    for n in notes:                                                           # lueur au point d'impact pendant que la note sonne
        if n.start <= t < n.end:
            px, pw, blk = xpos(n.pitch)
            col = LEFT if n.pitch < split else RIGHT
            x0, x1 = (px - a) * sx, (px + pw - a) * sx
            for k, f in enumerate((0.25, 0.45, 0.7)):
                g = tuple(int(c * (1 - f) + 255 * f) for c in col[0])
                d.rectangle([x0 - 6 + k * 3, ky - 46 + k * 14, x1 + 6 - k * 3, ky], fill=g)
    on = {n.pitch: (LEFT if n.pitch < split else RIGHT) for n in notes if n.start <= t < n.end}
    first, last = int(math.floor(a)) - 1, int(math.ceil(b)) + 1
    for p in range(0, 128):
        px, pw, blk = xpos(p)
        if blk or px + pw < a - 1 or px > b + 1:
            continue
        x0, x1 = (px - a) * sx, (px + pw - a) * sx
        col = on.get(p)
        d.rectangle([x0, ky, x1, H], fill=col[0] if col else (253, 252, 248))
        _sketch_line(d, x0 + 1, ky, x0 + 1, H, p, max(int(sx * 0.06), 3), amp=1.6 * (W / 1080))
    for p in range(0, 128):
        px, pw, blk = xpos(p)
        if not blk or px + pw < a - 1 or px > b + 1:
            continue
        x0, x1 = (px - a) * sx, (px + pw - a) * sx
        col = on.get(p)
        bh = KB_H * 0.62
        rk = random.Random(p)
        quad = _edges([(x0, ky), (x1, ky), (x1, ky + bh), (x0, ky + bh)], rk, 1.8 * (W / 1080), step=60)
        d.polygon(quad, fill=col[1] if col else (34, 33, 38))
        _stroke(d, quad, max(int(sx * 0.06), 3))
    _sketch_line(d, 0, ky, W, ky, 9001, 8, step=120, amp=2.5 * (W / 1080))
    _sketch_line(d, 0, H - 3, W, H - 3, 9002, 7, step=120, amp=2.0 * (W / 1080))
    for p in range(0, 128):                                                    # repères Do3 / Do4…
        if p % 12 == 0:
            px = xpos(p)[0]
            if a <= px < b and sx > 18 * (W / 1080):
                d.text(((px - a) * sx + sx * 0.5, H - 28), f"C{p // 12 - 1}", font=_font(int(min(sx * 0.4, 34))), fill=(120, 118, 124), anchor="ms")
    return img


def _title(img, title, subtitle, L: Layout, t: float = 0.0, duration: float = 1e9, hook: str = "", cta: str = ""):
    """Titre (coupé proprement sur 2 lignes, jamais hors cadre), compositeur, puis accroche au début et appel à l'action à la fin."""
    from app.renderer.compose import _wrap
    d = ImageDraw.Draw(img)
    wide = L.W > L.H
    f, lines = _wrap(d, title, 46 if wide else 56, L.W - 90, 2)
    top = 36 if wide else int(L.TOP * 0.18)
    y = top + f.size * 0.6
    for ln in lines:
        d.text((L.W / 2, y), ln, font=f, fill=INK, anchor="mm")
        y += f.size * 1.12
    if subtitle:
        d.text((L.W / 2, y + 6), subtitle, font=_font(30 if wide else 36), fill=(110, 108, 114), anchor="mm")
        y += 44
    msg = hook if t < 2.6 else (cta if duration - t < 3.2 else "")
    if msg:
        pf = _font(34 if wide else 42)
        w = d.textlength(msg, font=pf)
        if w > L.W - 80:
            pf = _font(28 if wide else 34)
            w = d.textlength(msg, font=pf)
        py = min(y + 52, L.TOP - 34) if not wide else y + 40
        d.rounded_rectangle([L.W / 2 - w / 2 - 28, py - 30, L.W / 2 + w / 2 + 28, py + 30], radius=30, fill=(248, 128, 90), outline=INK, width=4)
        d.text((L.W / 2, py), msg, font=pf, fill=(255, 255, 255), anchor="mm")


def clean_notes(notes):
    """Notes propres avant dessin : hauteurs valides, pas de doublon, pas de chevauchement sur une même touche, durée minimale.
    Évite les barres qui se superposent ou disparaissent (source d'erreurs visibles sur Synthesia)."""
    ns = sorted((n for n in notes if 21 <= n.pitch <= 108 and n.end > n.start), key=lambda n: (n.pitch, n.start))
    out = []
    for n in ns:
        if out and out[-1].pitch == n.pitch:
            prev = out[-1]
            if n.start - prev.start < 0.03:                                    # doublon
                if n.end > prev.end:
                    out[-1] = n
                continue
            if prev.end > n.start - 0.05:                                      # même touche rejouée : on laisse un petit creux visible
                out[-1] = type(prev)(prev.start, max(n.start - 0.05, prev.start + 0.08), prev.pitch, prev.velocity, prev.track, prev.channel)
        out.append(n)
    return sorted(out, key=lambda n: (n.start, n.pitch))


def verify_video(path, expected: float):
    """Contrôle du fichier produit : lisible, vidéo + audio, bonne durée. Lève une erreur sinon (le pipeline passe alors au rendu de secours)."""
    import json
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type:format=duration", "-of", "json", str(path)],
                       capture_output=True, text=True)
    try:
        info = json.loads(r.stdout)
        dur = float(info["format"]["duration"])
        kinds = {s["codec_type"] for s in info["streams"]}
    except Exception:
        raise RuntimeError("vidéo produite illisible")
    if kinds < {"video", "audio"}:
        raise RuntimeError("vidéo produite sans image ou sans son")
    if abs(dur - expected) > max(0.6, expected * 0.03):
        raise RuntimeError(f"durée incohérente ({dur:.1f}s au lieu de {expected:.1f}s)")


def measure_sync(path, notes, start: float, duration: float):
    """Décalage son/notes mesuré sur le fichier FINAL (après encodage) : (secondes, confiance). Sert de contrôle de bout en bout."""
    import tempfile
    import wave
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "a.wav"
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(path), "-vn", "-ac", "2", "-ar", str(synth.SR), str(wav)], capture_output=True)
        if r.returncode or not wav.exists():
            return 0.0, 0.0
        with wave.open(str(wav), "rb") as w:
            a = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32).reshape(-1, 2) / 32768
    return synth.onset_lag(a, notes, start, duration)


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
                 result: dict | None = None, audio: np.ndarray | None = None, view: str = "wide", supersample: int = 2, hook: str = "", cta: str = ""):
    ns = clean_notes([n for n in notes if n.end > start and n.start < start + duration])
    if not ns:
        raise ValueError("aucune note dans la section")
    rel = [type(n)(n.start - start, n.end - start, n.pitch, n.velocity, n.track, n.channel) for n in ns]
    cam = Camera(rel, layout.W, layout.H, view)
    ss = 2 if (supersample or 1) >= 2 else 1                    # 2 = dessin en double taille puis réduction exacte (rapide, traits lisses)
    big = Layout(layout.W * ss, layout.H * ss, layout.TOP * ss, layout.KB_H * ss) if ss > 1 else layout   # dessin plus grand puis réduit : traits lisses
    hand_split = hand_split if hand_split is not None else hand_split_for(rel)
    final = Path(out_path)
    out_path = final.with_name(final.stem + ".part.mp4")            # écrit sous un nom provisoire : jamais de fichier à moitié fini à la place d'une vidéo
    out_path.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "a.wav"
        progress.report("Son du piano", 2)
        synth.write_wav(wav, audio if audio is not None else synth.render_audio(ns, start, duration))
        progress.report("Dessin des images", 20)
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
               "-s", f"{layout.W}x{layout.H}", "-r", str(fps), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "veryfast",
               "-crf", "18", "-tune", "animation", "-pix_fmt", "yuv420p", "-af", "loudnorm=I=-14:TP=-1.5:LRA=9", "-ar", "44100", "-c:a", "aac", "-b:a", "192k", "-shortest",
               "-movflags", "+faststart", str(out_path)]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        limit = max(900.0, duration * 20)                           # garde-fou : un ffmpeg bloqué est arrêté au lieu de figer l'agent
        wd = threading.Timer(limit, lambda: p.poll() is None and p.kill())
        wd.daemon = True
        wd.start()
        try:
            written = 0
            for i in range(int(duration * fps)):
                if i % 15 == 0:
                    control.check()
                    if control.STOP_RECORD.is_set() and written >= int(5 * fps):
                        control.STOP_RECORD.clear()
                        break
                t = i / fps
                if i % fps == 0:
                    pct = 20 + 78 * i / max(int(duration * fps), 1)
                    progress.report("Dessin des images", pct)
                    if i and i % (fps * 15) == 0:
                        log.info("🎞 Dessin des images : %d%%", pct)
                img = render_frame(rel, t, cam.step(t, 1 / fps), big, hand_split)
                if ss > 1:
                    img = img.reduce(2)
                _title(img, title, subtitle, layout, t, duration, hook, cta)
                edge = min(t, duration - t)
                if edge < 0.5:                                                  # fondu d'entrée / sortie
                    img = Image.blend(Image.new("RGB", img.size, PAPER), img, max(edge / 0.5, 0.0))
                p.stdin.write(img.tobytes())
                written += 1
            if result is not None:
                result["duration"] = written / fps
            p.stdin.close()
            progress.report("Finalisation de la vidéo", 99)
            err = p.stderr.read().decode()[-400:]
            if p.wait() != 0:
                raise RuntimeError(f"ffmpeg: {err}")
            verify_video(out_path, written / fps)
            try:
                lag, conf = measure_sync(out_path, rel, 0.0, written / fps)
                if result is not None:
                    result["sync_ms"] = round(lag * 1000)
                if conf > 0.5 and abs(lag) > 0.04:
                    log.warning("⚠ Son décalé de %+d ms par rapport aux notes (contrôle final)", round(lag * 1000))
            except Exception:
                pass
            os.replace(out_path, final)
        except Exception:
            out_path.unlink(missing_ok=True)
            raise
        finally:
            wd.cancel()
            if p.poll() is None:
                p.kill()
    return final
