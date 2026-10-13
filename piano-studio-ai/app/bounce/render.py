"""Rendu « balle qui rebondit » dans le même style dessiné que le piano : plateformes qui s'allument à chaque note, balle, traînée, caméra qui descend."""
import colorsys
import logging
import math
import os
import subprocess
import tempfile
import threading
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from app.director import control, progress
from app.visualizer import sketch, synth
from app.visualizer.falling import VERTICAL, Layout
from . import choreo

log = logging.getLogger(__name__)
INK = (38, 36, 40)
PAD_W, PAD_H, BALL_R = 190, 30, 56
GLOW_T = 0.45                                  # durée de l'allumage d'une plateforme


def pitch_color(p: int):
    """Une couleur par note (12 teintes), vive comme les lames d'un xylophone."""
    h = (p % 12) / 12.0
    r, g, b = colorsys.hsv_to_rgb(h, 0.62, 0.98)
    return int(r * 255), int(g * 255), int(b * 255)


def _bg(W, H):
    """Fond de studio : dégradé chaud → froid, large faisceau de lumière, vignettage et grain fin (comme la lumière douce de la référence)."""
    rng = np.random.default_rng(3)
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None]
    xx = np.linspace(0, 1, W, dtype=np.float32)[None, :]
    top, bot = np.array([246, 226, 206], np.float32), np.array([176, 190, 226], np.float32)
    arr = top[None, None, :] * (1 - yy[:, :, None]) + bot[None, None, :] * yy[:, :, None]
    arr = np.repeat(arr, W, axis=1)
    beam = np.exp(-(((xx - 0.78) / 0.30 + (yy - 0.30) / 0.55) ** 2))            # faisceau de lumière en haut à droite
    arr += beam[:, :, None] * np.array([34, 28, 14], np.float32)[None, None, :]
    vig = 1 - 0.30 * (((xx - 0.5) / 0.75) ** 2 + ((yy - 0.5) / 0.85) ** 2)
    arr *= np.clip(vig, 0.55, 1)[:, :, None]
    arr += rng.normal(0, 0.7, (H, W, 1)).astype(np.float32)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")


_BG = {}


def background(W, H):
    k = (W, H)
    if k not in _BG:
        _BG[k] = _bg(W, H)
    return _BG[k].copy()


def _grad(w, h, c0, c1):
    """Dégradé vertical c0 (haut) → c1 (bas), RGBA opaque."""
    t = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
    a = np.array(c0, np.float32)[None, None, :] * (1 - t) + np.array(c1, np.float32)[None, None, :] * t
    arr = np.repeat(a, w, axis=1)
    return Image.fromarray(np.dstack([arr, np.full((h, w, 1), 255, np.float32)]).astype(np.uint8), "RGBA")


SUN = (-72.0, 128.0)            # direction des ombres : le soleil vient d'en haut à droite (comme dans la référence)
ROD = (-0.50, 0.86)             # direction des tiges qui retiennent les plateformes (vers le mur)


def _paddle_sprite(k, led=None, seed=1):
    """Lame en aluminium BROSSÉ avec épaisseur, tranche sombre, reflet et bande lumineuse (LED) le long du bord : grise au repos, colorée à l'impact."""
    w, h, th = int(PAD_W * k), int(PAD_H * k), int(16 * k)
    pad = int(8 * k)
    img = Image.new("RGBA", (w + 2 * pad, h + th + 2 * pad), (0, 0, 0, 0))
    side = _grad(w, th, (86, 92, 112), (44, 48, 64))
    img.paste(side, (pad, pad + h - int(th * 0.35)), Image.new("L", (w, th), 255))
    face = np.array(_grad(w, h, (240, 243, 250), (146, 154, 176)), np.float32)
    rng = np.random.default_rng(seed)
    streak = rng.normal(0, 1, (h, 1, 1)).astype(np.float32) * 5.0                      # stries de brossage horizontales
    streak2 = np.repeat(streak, w, axis=1) + rng.normal(0, 1.2, (h, w, 1)).astype(np.float32)
    face[:, :, :3] = np.clip(face[:, :, :3] + streak2, 0, 255)
    sheen = np.exp(-(((np.linspace(0, 1, w) - 0.30) / 0.14) ** 2)).astype(np.float32)[None, :, None] * 26   # bande de lumière en travers
    face[:, :, :3] = np.clip(face[:, :, :3] + sheen, 0, 255)
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w - 1, h - 1], radius=int(h * 0.42), fill=255)
    img.paste(Image.fromarray(face.astype(np.uint8), "RGBA"), (pad, pad), m)
    d = ImageDraw.Draw(img)
    ly = pad + int(h * 0.30)
    lc = (tuple(led) + (255,)) if led else (74, 80, 96, 255)
    d.rounded_rectangle([pad + int(18 * k), ly, pad + w - int(18 * k), ly + int(5 * k)], radius=int(2.5 * k), fill=lc)         # LED
    d.rounded_rectangle([pad + int(12 * k), pad + int(2 * k), pad + w - int(12 * k), pad + int(6 * k)], radius=int(2 * k), fill=(255, 255, 255, 170))
    d.rounded_rectangle([pad, pad, pad + w - 1, pad + h - 1], radius=int(h * 0.42), outline=(58, 62, 80, 235), width=max(int(2 * k), 1))
    return img


def _rod_sprite(k):
    """Tige métallique qui part de la plateforme vers le mur : cylindre dégradé avec reflet (vue oblique)."""
    L = int(210 * k)
    wd = int(11 * k)
    ang = math.atan2(ROD[1], ROD[0])
    img = Image.new("RGBA", (L + 40, int(L * 0.9) + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, y0 = 20, 20
    x1, y1 = x0 + ROD[0] * L, y0 + ROD[1] * L
    d.line([(x0 - ROD[0] * 0, y0), (x1 + L * 0.5, y1)], fill=(0, 0, 0, 0))
    ox, oy = int(abs(min(0, ROD[0])) * L) + 24, 20
    ex, ey = ox + ROD[0] * L, oy + ROD[1] * L
    d.line([(ox, oy), (ex, ey)], fill=(110, 116, 134, 255), width=wd)
    d.line([(ox - 2 * k, oy), (ex - 2 * k, ey)], fill=(176, 182, 198, 255), width=max(int(wd * 0.35), 1))
    d.ellipse([ex - wd, ey - wd, ex + wd, ey + wd], fill=(78, 84, 104, 255))
    img = img.crop((0, 0, int(ox + 30), int(ey + wd + 6))) if False else img
    return img, (ox, oy)


def _sprites(hit, k):
    """Sprites d'une plateforme (calculés UNE fois) : lame, lame allumée, halo, ombre portée oblique allongée, tige."""
    base = _paddle_sprite(k, None, seed=hit.pitch + 3)
    c = pitch_color(hit.pitch)
    lit = _paddle_sprite(k, tuple(min(255, int(x * 1.1 + 25)) for x in c), seed=hit.pitch + 3)
    deg = -math.degrees(hit.tilt)

    def rot(im):
        return im.rotate(deg, resample=Image.BICUBIC, expand=True)
    base_r, lit_r = rot(base), rot(lit)
    halo = Image.new("RGBA", (base.width + int(140 * k), base.height + int(140 * k)), (0, 0, 0, 0))
    ImageDraw.Draw(halo).rounded_rectangle([int(60 * k), int(60 * k), halo.width - int(60 * k), halo.height - int(60 * k)], radius=int(30 * k), fill=c + (255,))
    halo = rot(halo.filter(ImageFilter.GaussianBlur(int(28 * k))))
    alpha = base_r.getchannel("A")
    steps = 8                                                                   # ombre allongée : empreintes successives le long de la direction du soleil (max, pas d'addition)
    mx, my = int(abs(SUN[0]) * k) + 24, int(SUN[1] * k) + 24
    canvas = Image.new("L", (base_r.width + mx + 24, base_r.height + my + 24), 0)
    ox0, oy0 = int(abs(SUN[0]) * k) + 24, 24                                    # position de la lame (f = 0) dans le canevas
    for i in range(steps + 1):
        f = i / steps
        layer = Image.new("L", canvas.size, 0)
        layer.paste(alpha, (int(ox0 + SUN[0] * k * f), int(oy0 + SUN[1] * k * f)))
        canvas = ImageChops.lighter(canvas, layer)
    canvas = canvas.filter(ImageFilter.GaussianBlur(int(4 * k + 2)))
    shadow = Image.new("RGBA", canvas.size, (50, 54, 100, 0))
    shadow.putalpha(canvas.point(lambda v: int(v * 0.30)))
    anchor = (ox0 + base_r.width / 2, oy0 + base_r.height / 2)
    return {"base": base_r, "lit": lit_r, "halo": halo, "shadow": shadow, "anchor": anchor}


def _paste_center(img, spr, cx, cy):
    x0, y0 = int(round(cx - spr.width / 2)), int(round(cy - spr.height / 2))
    if 0 <= x0 and x0 + spr.width <= img.width and 0 <= y0 and y0 + spr.height <= img.height:
        img.alpha_composite(spr, (x0, y0))
        return
    sx0, sy0 = max(0, -x0), max(0, -y0)
    sx1, sy1 = min(spr.width, img.width - x0), min(spr.height, img.height - y0)
    if sx1 > sx0 and sy1 > sy0:
        img.alpha_composite(spr.crop((sx0, sy0, sx1, sy1)), (x0 + sx0, y0 + sy0))


def _ball_sprite(k, color, squash=1.0):
    """Bille de VERRE : tourbillon de deux couleurs à l'intérieur, reflet principal, reflet de fenêtre, lumière rebondie en bas, bord plus clair (effet fresnel)."""
    R = int(BALL_R * k)
    size = R * 2 + int(40 * k)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    cx = cy = size / 2
    dx, dy = (xx - cx) / R, (yy - cy) / R
    rr = np.sqrt(dx ** 2 + dy ** 2)
    inside = rr <= 1.0
    z = np.sqrt(np.clip(1 - rr ** 2, 0, 1))
    th = np.arctan2(dy, dx)
    sw = np.clip(0.5 + 0.5 * np.sin(2.0 * th + 4.0 * rr + 1.4 * np.sin(3.0 * rr + 1.0)), 0, 1)    # tourbillon doux
    sw = sw * sw * (3 - 2 * sw)
    h0, s0, v0 = colorsys.rgb_to_hsv(*[c / 255 for c in color])
    r2, g2, b2 = colorsys.hsv_to_rgb((h0 + 0.10) % 1.0, max(0.35, s0 - 0.15), min(1.0, v0 + 0.02))
    cA = np.array(color, np.float32)
    cB = np.array([r2, g2, b2], np.float32) * 255
    base = cA[None, None, :] * (1 - sw[:, :, None]) + cB[None, None, :] * sw[:, :, None]
    light = np.clip((-dx * 0.45 - dy * 0.65 + z * 0.62), 0, 1)
    col = base * (0.42 + 0.72 * light[:, :, None])
    col += (np.clip((dx * 0.1 + dy * 0.75), 0, 1) ** 2)[:, :, None] * np.array([90, 80, 60], np.float32)[None, None, :] * 0.5
    fres = np.clip((rr - 0.70) / 0.30, 0, 1) ** 2
    col += fres[:, :, None] * np.array([70, 80, 100], np.float32)[None, None, :] * 0.6
    spec = np.exp(-(((dx + 0.36) / 0.18) ** 2 + ((dy + 0.46) / 0.12) ** 2))
    win = np.exp(-(((dx - 0.30) / 0.30) ** 2 + ((dy - 0.28) / 0.08) ** 2)) * 0.35
    col += (spec * 255 + win * 255)[:, :, None]
    col *= (1 - 0.35 * np.clip((rr - 0.93) / 0.07, 0, 1))[:, :, None]
    alpha = np.clip((1.0 - rr) * R / (1.6 * k) + 0.5, 0, 1) * inside
    img = Image.fromarray(np.dstack([np.clip(col, 0, 255), alpha * 255]).astype(np.uint8), "RGBA")
    if squash != 1.0:
        w, h = img.size
        img = img.resize((int(w * (2 - squash) ** 0.5), int(h * squash)), Image.BICUBIC)
    return img


_BALLS = {}


def ball_sprite(k, pitch, squash):
    key = (k, pitch % 12, round(squash, 2))
    if key not in _BALLS:
        _BALLS[key] = _ball_sprite(k, pitch_color(pitch), squash)
    return _BALLS[key]


class Cache:
    """Sprites pré-calculés pour une vidéo + décor flou : arrière-plan lointain (parallaxe 0,5) et gros plan flou sur les bords (parallaxe 1,5) pour la profondeur."""

    def __init__(self, hits, k, W, H, seed=0):
        self.k = k
        self.sp = {id(h): _sprites(h, k) for h in hits}
        rnd = np.random.default_rng(seed + 11)
        far, near = [], []
        y = hits[0].y - 900
        while y < hits[-1].y + 1400:
            far.append((float(rnd.uniform(60, W - 60)), y, float(rnd.uniform(-0.6, 0.6))))
            y += float(rnd.uniform(170, 300))
        y = hits[0].y - 1200
        while y < hits[-1].y + 1600:
            near.append((float(rnd.choice([rnd.uniform(-60, 130), rnd.uniform(W - 130, W + 60)])), y, float(rnd.uniform(-0.8, 0.8))))
            y += float(rnd.uniform(520, 900))
        self.far, self.near = far, near
        self.rod = _rod_sprite(k)
        spr = _paddle_sprite(k * 0.55).filter(ImageFilter.GaussianBlur(int(5 * k)))
        r = spr.split()
        spr = Image.merge("RGBA", [r[0].point(lambda v: int(v * 0.6 + 70)), r[1].point(lambda v: int(v * 0.6 + 75)), r[2].point(lambda v: int(v * 0.62 + 90)), r[3].point(lambda v: int(v * 0.55))])
        big = _paddle_sprite(k * 1.7).filter(ImageFilter.GaussianBlur(int(15 * k)))
        rb = big.split()
        big = Image.merge("RGBA", [rb[0], rb[1], rb[2], rb[3].point(lambda v: int(v * 0.55))])
        self.far_spr = {ang: spr.rotate(-math.degrees(ang), resample=Image.BICUBIC, expand=True) for ang in sorted({round(a, 1) for _, _, a in far})}
        self.near_spr = {ang: big.rotate(-math.degrees(ang), resample=Image.BICUBIC, expand=True) for ang in sorted({round(a, 1) for _, _, a in near})}


def _fx_layer(size, hits_now, t, cam_y, k):
    """Étincelles + onde de choc des impacts récents, dessinées sur une couche transparente puis fondues (vrai mélange, pas de pixels écrasés)."""
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for h in hits_now:
        age = t - h.t
        c = pitch_color(h.pitch)
        if age < 0.35:
            ring = 44 + age / 0.35 * 150
            a = 1 - age / 0.35
            d.ellipse([(h.x - ring) * k, (h.y - cam_y - ring * 0.45) * k, (h.x + ring) * k, (h.y - cam_y + ring * 0.45) * k],
                      outline=c + (int(220 * a),), width=max(int(7 * a * k), 1))
        if age < 0.55:
            n = (math.sin(h.tilt), -math.cos(h.tilt))
            import random as _r
            rnd = _r.Random(int(h.t * 1000) + h.pitch)
            for j in range(10):                                                          # étincelles qui jaillissent de l'impact
                ang = math.atan2(n[1], n[0]) + rnd.uniform(-1.1, 1.1)
                sp = rnd.uniform(260, 620)
                vx, vy = math.cos(ang) * sp, math.sin(ang) * sp
                x = h.x + vx * age
                y = h.y + vy * age + 0.5 * 1500 * age * age - cam_y
                life = 1 - age / 0.55
                r = (4 + rnd.uniform(0, 4)) * life
                col = tuple(min(255, int(c[i] * 0.5 + 255 * 0.5)) for i in range(3))
                d.ellipse([(x - r) * k, (y - r) * k, (x + r) * k, (y + r) * k], fill=col + (int(255 * life),))
    return layer


def render_frame(hits, t, cam_y, L: Layout, ball, ss=1.0, trail=(), cache: "Cache" = None, ball_fn=None):
    W, H = L.W, L.H
    k = ss
    cache = cache or Cache(hits, k, W, H)
    img = background(int(W * k), int(H * k))
    recent = [h for h in hits if 0 <= t - h.t < 0.55]
    if recent and t - recent[-1].t < 0.12:                                                  # flash de lumière à chaque note
        f = 1 - (t - recent[-1].t) / 0.12
        img.alpha_composite(Image.new("RGBA", img.size, (255, 244, 224, int(26 * f))))
    for fx, fy, fa in cache.far:                                                             # décor lointain flou (parallaxe 0,5)
        sy = (fy - cam_y) * 0.5 + H * 0.25
        if -200 < sy < H + 200:
            _paste_center(img, cache.far_spr[round(fa, 1)], fx * k, sy * k)
    view_top, view_bot = cam_y - 500, cam_y + H + 500
    vis = [h for h in hits if view_top <= h.y <= view_bot]
    pads = []
    for h in vis:
        sp = cache.sp[id(h)]
        n = (math.sin(h.tilt), -math.cos(h.tilt))
        age = t - h.t
        recoil = 10 * max(0.0, 1 - age / 0.18) if 0 <= age < 0.18 else 0.0                  # la lame s'enfonce à l'impact puis revient
        cx = h.x - n[0] * (BALL_R + PAD_H / 2) - n[0] * recoil
        cy = h.y - n[1] * (BALL_R + PAD_H / 2) - n[1] * recoil - cam_y
        pads.append((h, sp, cx, cy, age))
        _paste_clipped_at(img, sp["shadow"], cx * k - sp["anchor"][0], cy * k - sp["anchor"][1])
    rod, (rox, roy) = cache.rod
    for h, sp, cx, cy, age in pads:                                                          # tiges
        img.alpha_composite(rod, (int(cx * k - rox), int(cy * k - roy))) if (
            0 <= cx * k - rox and 0 <= cy * k - roy and cx * k - rox + rod.width < img.width and cy * k - roy + rod.height < img.height) else _paste_clipped_at(img, rod, cx * k - rox, cy * k - roy)
    for h, sp, cx, cy, age in pads:
        glow = max(0.0, 1 - age / GLOW_T) if 0 <= age <= GLOW_T else 0.0
        if glow > 0:
            halo = sp["halo"].copy()
            halo.putalpha(halo.getchannel("A").point(lambda v, g=glow: int(v * g * 0.9)))
            _paste_center(img, halo, cx * k, cy * k)
        _paste_center(img, sp["base"] if glow <= 0 else Image.blend(sp["base"], sp["lit"], min(1.0, glow * 1.2)), cx * k, cy * k)
    near = min(hits, key=lambda h: abs(h.t - t))
    for i, (tx, ty) in enumerate(trail):                                                     # traînée de mouvement
        a = (i + 1) / (len(trail) + 1)
        spr = ball_sprite(k, near.pitch, 1.0)
        tr = spr.resize((int(spr.width * (0.35 + 0.45 * a)), int(spr.height * (0.35 + 0.45 * a))), Image.BILINEAR)
        tr.putalpha(tr.getchannel("A").point(lambda v, aa=a: int(v * aa * 0.24)))
        _paste_center(img, tr, tx * k, (ty - cam_y) * k)
    bx, by = ball
    squash = 1.0
    if abs(t - near.t) < 0.07:
        squash = 0.78 + 0.22 * abs(t - near.t) / 0.07                                        # la bille s'écrase à l'impact
    m = int(40 * k)
    sh = Image.new("RGBA", (int(BALL_R * 2.6 * k) + 2 * m, int(BALL_R * 1.2 * k) + 2 * m), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse([m, m, sh.width - m, sh.height - m], fill=(52, 56, 104, 105))
    _paste_center(img, sh.filter(ImageFilter.GaussianBlur(int(12 * k))), (bx + 30) * k, (by - cam_y + BALL_R * 1.25) * k)
    _paste_center(img, ball_sprite(k, near.pitch, squash), bx * k, (by - cam_y) * k)
    fx = [h for h in hits if 0 <= t - h.t < 0.55 and view_top <= h.y <= view_bot]
    if fx:
        img.alpha_composite(_fx_layer(img.size, fx, t, cam_y, k))
    for fx_, fy_, fa_ in cache.near:                                                         # gros plan flou sur les bords (parallaxe 1,5)
        sy = (fy_ - cam_y) * 1.5 + H * 0.15
        if -300 < sy < H + 300:
            _paste_center(img, cache.near_spr[round(fa_, 1)], fx_ * k, sy * k)
    out = img.convert("RGB")
    return out if k == 1 else out.reduce(int(k))


def _paste_clipped_at(img, spr, x, y):
    x0, y0 = int(round(x)), int(round(y))
    sx0, sy0 = max(0, -x0), max(0, -y0)
    sx1, sy1 = min(spr.width, img.width - x0), min(spr.height, img.height - y0)
    if sx1 > sx0 and sy1 > sy0:
        img.alpha_composite(spr.crop((sx0, sy0, sx1, sy1)), (x0 + sx0, y0 + sy0))


def _title(img, label, subtitle, L: Layout):
    d = ImageDraw.Draw(img)
    f = sketch._font(78)
    for dx, dy in ((-3, 0), (3, 0), (0, -3), (0, 3), (-2, -2), (2, 2), (-2, 2), (2, -2)):
        d.text((L.W / 2 + dx, 240 + dy), label, font=f, fill=(30, 28, 40), anchor="mm")
    d.text((L.W / 2, 240), label, font=f, fill=(255, 255, 255), anchor="mm")
    if subtitle:
        f2 = sketch._font(40)
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            d.text((L.W / 2 + dx, 320 + dy), subtitle, font=f2, fill=(30, 28, 40), anchor="mm")
        d.text((L.W / 2, 320), subtitle, font=f2, fill=(255, 255, 255), anchor="mm")


def frames_positions(hits, fps, total):
    return [choreo.ball_at(hits, i / fps) for i in range(total)]


def camera_path(ball_ys, fps, sigma=0.32, anchor=0.46, H=1920):
    """Caméra : suit la balle en douceur (lissage gaussien), jamais saccadée."""
    ys = np.array(ball_ys, dtype=np.float64)
    r = int(sigma * fps * 3)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / (sigma * fps)) ** 2)
    k /= k.sum()
    pad = np.pad(ys, r, mode="edge")
    sm = np.convolve(pad, k, mode="valid")
    return sm - H * anchor


def render_video(all_notes, onsets, out_path, label, subtitle="", start=0.0, duration=None, fps=30, layout: Layout = VERTICAL,
                 result=None, audio=None, supersample=2, seed=0):
    """`all_notes` = toutes les notes (le son complet), `onsets` = [(t, pitch)] de la mélodie (les rebonds)."""
    hits = choreo.build(onsets, width=layout.W, seed=seed)
    if not hits:
        raise ValueError("aucune note à animer")
    duration = duration or (hits[-1].t + 2.2)
    total = int(duration * fps)
    ball = frames_positions(hits, fps, total)
    cam = camera_path([b[1] for b in ball], fps, H=layout.H)
    final = Path(out_path)
    part = final.with_name(final.stem + ".part.mp4")
    part.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "a.wav"
        progress.report("Son du piano", 2)
        notes_rel = [type(n)(n.start - start, n.end - start, n.pitch, n.velocity, n.track, n.channel) for n in all_notes
                     if n.end > start and n.start < start + duration]
        synth.write_wav(wav, audio if audio is not None else synth.render_audio(all_notes, start, duration))
        progress.report("Dessin des images", 20)
        ss = 2 if (supersample or 1) >= 2 else 1
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{layout.W}x{layout.H}",
               "-r", str(fps), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-tune", "animation",
               "-profile:v", "high", "-pix_fmt", "yuv420p", "-af", "loudnorm=I=-14:TP=-1.5:LRA=9", "-ar", "44100", "-c:a", "aac", "-b:a", "256k",
               "-shortest", "-movflags", "+faststart", str(part)]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        limit = max(900.0, duration * 20)
        wd = threading.Timer(limit, lambda: p.poll() is None and p.kill())
        wd.daemon = True
        wd.start()
        try:
            written = 0
            trail_n = 7
            cache = Cache(hits, ss, layout.W, layout.H, seed)
            for i in range(total):
                if i % 15 == 0:
                    control.check()
                t = i / fps
                if i % fps == 0:
                    progress.report("Dessin des images", 20 + 78 * i / max(total, 1))
                trail = [(ball[j][0], ball[j][1]) for j in range(max(0, i - trail_n * 2), i, 2)]
                img = render_frame(hits, t, cam[i], layout, ball[i], ss, [(x, y) for x, y in trail], cache)
                _title(img, label, subtitle, layout)
                edge = min(t, duration - t)
                if edge < 0.4:
                    img = Image.blend(Image.new("RGB", img.size, (246, 226, 206)), img, max(edge / 0.4, 0.0))
                p.stdin.write(img.tobytes())
                written += 1
            if result is not None:
                result["duration"] = written / fps
            p.stdin.close()
            progress.report("Finalisation de la vidéo", 99)
            err = p.stderr.read().decode()[-400:]
            if p.wait() != 0:
                raise RuntimeError(f"ffmpeg: {err}")
            sketch.verify_video(part, written / fps)
            os.replace(part, final)
        except Exception:
            part.unlink(missing_ok=True)
            raise
        finally:
            wd.cancel()
            if p.poll() is None:
                p.kill()
    return final
