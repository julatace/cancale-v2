from collections import Counter
from .parser import Note

_MAJ = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_MIN = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
SPLIT = 60  # < C4 = main gauche


def _corr(a, b):
    ma, mb = sum(a) / 12, sum(b) / 12
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
    return num / den if den else 0


def estimate_key(notes: list[Note]) -> str:
    hist = [0.0] * 12
    for n in notes:
        hist[n.pitch % 12] += n.end - n.start
    best = max(((_corr(hist, [prof[(i - r) % 12] for i in range(12)]), r, m)
                for r in range(12) for m, prof in (("major", _MAJ), ("minor", _MIN))))
    return f"{_NAMES[best[1]]} {best[2]}"


def polyphony(notes: list[Note]) -> int:
    ev = sorted([(n.start, 1) for n in notes] + [(n.end, -1) for n in notes], key=lambda e: (e[0], e[1]))
    cur = peak = 0
    for _, d in ev:
        cur += d; peak = max(peak, cur)
    return peak


def window_features(notes, start, end) -> dict:
    ns = [n for n in notes if n.start < end and n.end > start]
    onsets = [n for n in ns if start <= n.start < end]
    dur = end - start
    covered = 0.0
    last = start
    for n in sorted(ns, key=lambda n: n.start):
        s, e = max(n.start, last), min(n.end, end)
        if e > s:
            covered += e - s; last = e
    both = {n.pitch < SPLIT for n in onsets}
    return {
        "density": len(onsets) / dur,
        "silence_ratio": 1 - covered / dur,
        "poly": polyphony(ns) if ns else 0,
        "pitch_span": (max(n.pitch for n in onsets) - min(n.pitch for n in onsets)) if onsets else 0,
        "two_hands": len(both) == 2,
        "avg_vel": sum(n.velocity for n in onsets) / len(onsets) if onsets else 0,
    }


def analyze(notes: list[Note], tempo_map) -> dict:
    if not notes:
        raise ValueError("aucune note")
    dur = max(n.end for n in notes)
    chords = Counter(round(n.start, 2) for n in notes)
    return {
        "bpm": round(tempo_map[0][1], 1),
        "key": estimate_key(notes),
        "note_count": len(notes),
        "duration": round(dur, 2),
        "avg_density": round(len(notes) / dur, 2),
        "avg_velocity": round(sum(n.velocity for n in notes) / len(notes), 1),
        "max_polyphony": polyphony(notes),
        "left_hand_notes": sum(n.pitch < SPLIT for n in notes),
        "right_hand_notes": sum(n.pitch >= SPLIT for n in notes),
        "chord_count": sum(1 for c in chords.values() if c >= 3),
    }


def viral_score(f: dict) -> float:
    """0-100 : densité visuelle, ampleur, deux mains, énergie, peu de silence."""
    s = min(f["density"] / 8, 1) * 40 + min(f["pitch_span"] / 36, 1) * 15 \
        + (10 if f["two_hands"] else 0) + min(f["avg_vel"] / 100, 1) * 15 \
        + min(f["poly"] / 6, 1) * 10 + (1 - f["silence_ratio"]) * 10
    return round(s, 1)
