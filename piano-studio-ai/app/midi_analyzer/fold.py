from dataclasses import replace


def fold_notes(notes, lowest: int, n_keys: int):
    """Ramène chaque note dans [lowest, lowest+n_keys-1] par octaves (même nom de note)."""
    hi = lowest + n_keys - 1
    out = []
    for n in notes:
        p = n.pitch
        while p < lowest: p += 12
        while p > hi: p -= 12
        out.append(replace(n, pitch=p))
    return out


def choose_lowest(notes, n_keys: int, floor: int = 21, ceil: int = 108) -> int:
    """Début (toujours un Do) de la plage de n_keys touches qui contient le plus de notes (pondérées par la durée)."""
    best, best_score = 48, -1.0
    for lo in range(24, ceil - n_keys + 2, 12):
        hi = lo + n_keys - 1
        score = sum(min(n.end - n.start, 2.0) for n in notes if lo <= n.pitch <= hi)
        score -= abs((lo + hi) / 2 - 60) * 1e-3                 # à égalité : plage proche du milieu du piano
        if score > best_score:
            best, best_score = lo, score
    return max(best, floor)


def choose_span(notes, min_keys: int = 36, max_keys: int = 60, floor: int = 21, ceil: int = 108) -> tuple[int, int]:
    """(plus bas Do, nombre de touches) : l'étendue réelle du morceau (98 % des notes), arrondie à des octaves entières, entre
    min_keys et max_keys. Les notes rares hors étendue sont ramenées par octave ; si le morceau est plus large que max_keys,
    on garde la fenêtre qui contient le plus de notes."""
    if not notes:
        return 48, min_keys
    ps = sorted(n.pitch for n in notes)
    lo_p, hi_p = ps[int(len(ps) * 0.01)], ps[min(int(len(ps) * 0.99), len(ps) - 1)]
    lowest = max((lo_p // 12) * 12, floor // 12 * 12 + (12 if floor % 12 else 0))
    span = hi_p - lowest + 1
    keys = ((span + 11) // 12) * 12
    if keys > max_keys:
        return choose_lowest(notes, max_keys, floor, ceil), max_keys
    if keys < min_keys:                                         # morceau étroit : on garde le minimum, centré sur les notes
        return choose_lowest(notes, min_keys, floor, ceil), min_keys
    return lowest, min(keys, ceil - lowest + 1)
