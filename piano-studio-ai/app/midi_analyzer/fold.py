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
