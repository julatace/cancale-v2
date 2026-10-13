"""Chorégraphie « balle qui rebondit » : une plateforme par note de la mélodie, la balle tombe sur chacune EXACTEMENT au temps de la note.
Tout est calculé à la main (trajectoires paraboliques), donc la synchro avec le son est exacte, sans simulateur physique."""
import math
from dataclasses import dataclass, field


@dataclass
class Hit:
    t: float                 # instant de l'impact (= début de la note)
    pitch: int
    x: float
    y: float                 # position de l'impact (monde, y vers le bas)
    tilt: float = 0.0        # inclinaison de la plateforme (radians) : normale = direction de renvoi de la balle
    seg: tuple = field(default_factory=tuple)   # (vx, vy0, g) du vol qui PART de cet impact


def melody_onsets(notes, min_gap: float = 0.16, max_notes: int = 400):
    """Une note par attaque : la plus aiguë d'un accord (la mélodie), en écartant celles qui sont trop proches (< min_gap) pour être suivies à l'œil."""
    ns = sorted(notes, key=lambda n: (n.start, -n.pitch))
    out = []
    for n in ns:
        if out and n.start - out[-1][0] < 0.04:               # accord : on garde la plus aiguë (déjà la première grâce au tri)
            continue
        if out and n.start - out[-1][0] < min_gap:
            continue
        out.append((n.start, n.pitch))
        if len(out) >= max_notes:
            break
    return out


def build(onsets, width: float = 1080, margin: float = 150, h: float = 95, drop: float = 150, lead: float = 1.2, seed: int = 0):
    """Retourne la liste des `Hit`. `lead` = durée de chute de la balle avant la 1re note.
    Pour chaque vol i -> i+1 de durée Δ : le rebond monte de `h` au-dessus de la plateforme puis retombe de `drop` plus bas au temps exact.
    Équation : drop = -sqrt(2 g h) Δ + g Δ²/2  =>  g = (sqrt(2h) + sqrt(2h + 2 drop))² / Δ²."""
    import random
    rnd = random.Random(seed)
    if not onsets:
        return []
    pitches = [p for _, p in onsets]
    lo, hi = min(pitches), max(pitches)
    span = max(hi - lo, 1)
    xs = []
    for i, (t, p) in enumerate(onsets):                      # x suit la hauteur de la note (aigu = à droite), avec un peu de variété
        base = margin + (p - lo) / span * (width - 2 * margin)
        jitter = rnd.uniform(-35, 35) if i else 0
        xs.append(min(max(base + jitter, margin), width - margin))
    hits = []
    y = 0.0
    for i, (t, p) in enumerate(onsets):
        hits.append(Hit(t=t, pitch=p, x=xs[i], y=y))
        y += drop + (20 * ((p - lo) / span))                 # un peu plus de chute pour les notes aiguës : parcours moins régulier
    for i in range(len(hits) - 1):
        a, b = hits[i], hits[i + 1]
        dt = max(b.t - a.t, 1e-3)
        d = b.y - a.y
        s = math.sqrt(2 * h)
        g = (s + math.sqrt(2 * h + 2 * d)) ** 2 / dt ** 2
        vy0 = -math.sqrt(2 * g * h)
        a.seg = ((b.x - a.x) / dt, vy0, g)
    # inclinaison : la plateforme est perpendiculaire à (v_sortie - v_entrée) : le rebond est alors un vrai « miroir »
    prev_v = None
    for i, a in enumerate(hits):
        if a.seg:
            vx, vy, g = a.seg
        else:
            vx, vy, g = 0.0, -math.sqrt(2 * 2 * h * 900), 900.0
        if prev_v is None:                                   # 1re plateforme : la balle tombe tout droit
            fall_g = 2 * (0 + 0) or 1
            vin = (0.0, math.sqrt(2 * 1800 * 0))
            vin = (0.0, 900.0)
        else:
            vin = prev_v
        dx, dy = vx - vin[0], vy - vin[1]
        a.tilt = math.atan2(dx, -dy) if (dx or dy) else 0.0   # angle de la plateforme par rapport à l'horizontale
        a.tilt = max(-0.7, min(0.7, a.tilt))
        if i + 1 < len(hits):
            dt = max(hits[i + 1].t - a.t, 1e-3)
            prev_v = (vx, vy + g * dt)                        # vitesse à l'arrivée sur la plateforme suivante
    return hits


def ball_at(hits, t: float, lead: float = 1.2, g0: float = 1800.0):
    """Position (x, y) de la balle à l'instant t. Avant la 1re note : chute verticale arrivant exactement sur la 1re plateforme."""
    if not hits:
        return 0.0, 0.0
    first = hits[0]
    if t <= first.t:
        # chute libre depuis le haut, arrivée exacte à first.t : y = first.y - 0.5 g (first.t - t)²  avec une vitesse d'arrivée raisonnable
        tau = first.t - t
        g = g0
        return first.x, first.y - 0.5 * g * tau * tau
    if t >= hits[-1].t:                                       # après la dernière note : la balle retombe et sort de l'écran
        last = hits[-1]
        tau = t - last.t
        return last.x, last.y - 95 * 0 + 0.5 * 1800 * tau * tau - 600 * tau
    lo, hi = 0, len(hits) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if hits[mid].t <= t:
            lo = mid
        else:
            hi = mid
    a = hits[lo]
    vx, vy0, g = a.seg
    tau = t - a.t
    return a.x + vx * tau, a.y + vy0 * tau + 0.5 * g * tau * tau
