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
