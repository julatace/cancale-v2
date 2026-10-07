"""Refrain : le passage que tout le monde reconnaît = le thème mélodique qui revient le plus souvent dans le morceau."""
import math
from collections import Counter

from app.midi_analyzer.analyzer import viral_score, window_features
from app.section_selector.selector import MAX_SILENCE, select_section

NGRAM = 6        # un thème = une suite de 6 intervalles mélodiques identiques (indépendant de la tonalité)


def melody(notes, gap: float = 0.08) -> list[tuple[float, int]]:
    """Mélodie = la note la plus aiguë de chaque attaque (notes jouées ensemble regroupées)."""
    out, cur = [], None
    for n in sorted(notes, key=lambda n: n.start):
        if cur is not None and n.start - cur[0] < gap:
            cur = (cur[0], max(cur[1], n.pitch))
        else:
            if cur is not None: out.append(cur)
            cur = (n.start, n.pitch)
    if cur is not None: out.append(cur)
    return out


def repetition(mel) -> tuple[list[int], list[tuple]]:
    """Pour chaque note de la mélodie : combien de fois son motif (suite d'intervalles) est REPRIS ailleurs dans le morceau."""
    iv = [max(-12, min(12, mel[i + 1][1] - mel[i][1])) for i in range(len(mel) - 1)]
    keys = [tuple(iv[i:i + NGRAM]) for i in range(len(iv) - NGRAM + 1)]
    cnt = Counter(k for k in keys if len(set(k)) > 1)               # on écarte les répétitions d'une même note
    rep = [0] * len(mel)
    for i, k in enumerate(keys):
        c = cnt.get(k, 0)
        if c > 1:
            for j in range(i, i + NGRAM + 1):
                rep[j] = max(rep[j], c - 1)
    return rep, keys


def select_hook(notes, target: float = 60, step: float = 1.0) -> dict:
    """Fenêtre de `target` secondes contenant le plus de reprises du thème, départ calé sur le début d'une phrase répétée.
    Retourne le même format que select_section ; se replie sur lui s'il n'y a pas de répétition nette."""
    total = max(n.end for n in notes)
    target = min(target, total)
    mel = melody(notes)
    if len(mel) < NGRAM * 3:
        return select_section(notes, target, step)
    rep, keys = repetition(mel)
    if max(rep) == 0:
        return select_section(notes, target, step)
    times = [t for t, _ in mel]
    best, start = None, 0.0
    while start + target <= total + 1e-9:
        f = window_features(notes, start, start + target)
        if f["silence_ratio"] <= MAX_SILENCE:
            idx = [i for i, t in enumerate(times) if start <= t < start + target]
            r = sum(1 for i in idx if rep[i] > 0) / max(len(idx), 1)          # part de la fenêtre faite de motifs repris
            reps = max((rep[i] for i in idx), default=0)
            score = 0.7 * r + 0.3 * viral_score(f) / 100 + 0.02 * math.log1p(reps)
            if best is None or score > best[0]:
                best = (score, start, f, reps, r)
        start += step
    if best is None:
        return select_section(notes, target, step)
    score, start, f, reps, share = best
    for i, t in enumerate(times):                                           # départ au début d'une phrase répétée (juste avant)
        if start - 1.0 <= t <= start + 4.0 and rep[i] > 0 and (i == 0 or rep[i - 1] == 0):
            start = max(0.0, t - 0.25)
            break
    start = min(start, max(total - target, 0.0))
    return {"start": round(start, 1), "end": round(start + target, 1), "duration": round(target, 1), "score": round(score * 100),
            "density": round(f["density"], 2),
            "reason": f"refrain repéré (thème repris {reps + 1} fois, {round(share * 100)} % du passage)"}
