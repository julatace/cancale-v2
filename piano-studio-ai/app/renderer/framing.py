"""Cadrage : zoom sur la partie du clavier réellement jouée, à partir de la fenêtre Synthesia pleine taille."""
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
                  aspect: float = 1080 / 1620, margin_keys: int = 1):
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
