"""Cadrage : zoom sur la partie du clavier réellement jouée, à partir de la fenêtre Synthesia pleine taille.
La zone est MESURÉE dans l'enregistrement (où les notes tombent), sans supposer quel clavier Synthesia affiche."""
import subprocess

import numpy as np

_WHITE = {0, 2, 4, 5, 7, 9, 11}


def _white_before(p: int) -> int:
    return sum(1 for q in range(p) if q % 12 in _WHITE)


def key_x(pitch: int, display_lo: int = 21, display_keys: int = 88) -> float:
    """Position horizontale (0..1) d'une touche dans le clavier affiché (touches blanches régulièrement espacées)."""
    hi = display_lo + display_keys - 1
    n_white = _white_before(hi + 1) - _white_before(display_lo)
    pos = _white_before(pitch) - _white_before(display_lo) + (0.5 if pitch % 12 in _WHITE else 0.0)
    return min(max(pos / n_white, 0.0), 1.0)


def vertical_crop(content, screen_pts, lo: int, hi: int, display_lo: int = 21, display_keys: int = 88,
                  aspect: float = 1080 / 1620, margin_keys: int = 6):
    """Zone (x, y, w, h) en fractions de l'image capturée : les touches lo..hi (+ marge) sur toute la hauteur utile,
    au rapport `aspect` (largeur/hauteur) quand l'écran le permet. Le bas (clavier) est toujours conservé. Si la hauteur disponible
    ne suffit pas, on garde TOUTES les touches jouées (la zone est un peu plus large que `aspect`, le montage met alors de légères bandes)."""
    cx, cy, cw, ch = content
    sw, sh = screen_pts
    x0 = key_x(lo - margin_keys, display_lo, display_keys)
    x1 = key_x(hi + margin_keys, display_lo, display_keys)
    w_pts, h_pts = (x1 - x0) * cw * sw, ch * sh
    if w_pts / h_pts < aspect:                              # trop étroit : on élargit autour du centre
        extra = (h_pts * aspect - w_pts) / (cw * sw)
        x0, x1 = x0 - extra / 2, x1 + extra / 2
    else:                                                   # trop large : on réduit la hauteur par le haut
        h_pts = w_pts / aspect
    if x0 < 0: x0, x1 = 0.0, min(x1 - x0, 1.0)
    if x1 > 1: x0, x1 = max(x0 - (x1 - 1), 0.0), 1.0
    h_frac = min(h_pts / sh, ch)
    return (cx + cw * x0, cy + ch - h_frac, cw * (x1 - x0), h_frac)


def crop_from_range(content, screen_pts, x0: float, x1: float, aspect: float):
    """Zone (x, y, w, h) en fractions de l'image capturée pour la bande horizontale [x0, x1] (fractions de la zone de contenu)."""
    cx, cy, cw, ch = content
    sw, sh = screen_pts
    w_pts, h_pts = (x1 - x0) * cw * sw, ch * sh
    if w_pts / h_pts < aspect:
        extra = (h_pts * aspect - w_pts) / (cw * sw)
        x0, x1 = x0 - extra / 2, x1 + extra / 2
    else:
        h_pts = w_pts / aspect
    if x0 < 0: x0, x1 = 0.0, min(x1 - x0, 1.0)
    if x1 > 1: x0, x1 = max(x0 - (x1 - 1), 0.0), 1.0
    h_frac = min(h_pts / sh, ch)
    return (cx + cw * x0, cy + ch - h_frac, cw * (x1 - x0), h_frac)


def measure_played_range(capture, trim: float, content, seconds: float = 60.0, fps: int = 4, keyboard_share: float = 0.22,
                         margin: float = 0.22, run=subprocess.run):
    """Mesure, dans l'enregistrement, la bande horizontale où les notes tombent : (x0, x1) en fractions de la zone de contenu,
    marge comprise. Les notes sont les seuls éléments colorés sur le fond gris. Retourne None si rien n'est détecté."""
    cx, cy, cw, ch = content
    vf = (f"crop=iw*{cw:.4f}:ih*{ch:.4f}:iw*{cx:.4f}:ih*{cy:.4f},fps={fps},scale=320:240")
    try:
        r = run(["ffmpeg", "-v", "error", "-ss", str(trim), "-t", str(seconds), "-i", str(capture), "-vf", vf,
                 "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True, timeout=180)
    except Exception:
        return None
    n = len(r.stdout) // (320 * 240 * 3)
    if n < 4:
        return None
    fr = np.frombuffer(r.stdout[: n * 320 * 240 * 3], np.uint8).reshape(n, 240, 320, 3).astype(np.float32)
    area = fr[:, : int(240 * (1 - keyboard_share)), :, :]                    # au-dessus du clavier : les notes qui tombent
    mx, mn = area.max(axis=3), area.min(axis=3)
    mask = ((mx - mn) > 0.45 * np.maximum(mx, 1)) & (mx > 90)                 # coloré (saturé) et lumineux, contrairement au fond gris
    col = mask.sum(axis=(0, 1)).astype(np.float64)
    total = col.sum()
    if total < 50:
        return None
    cum = np.cumsum(col) / total
    lo = int(np.searchsorted(cum, 0.004))                                     # on ignore les 0,4 % extrêmes (poussières)
    hi = int(np.searchsorted(cum, 0.996))
    x0, x1 = lo / 320.0, (hi + 1) / 320.0
    pad = max((x1 - x0) * margin, 0.03)
    return max(x0 - pad, 0.0), min(x1 + pad, 1.0)
