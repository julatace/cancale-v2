from app.midi_analyzer.analyzer import viral_score, window_features
from app.midi_analyzer.parser import Note

MAX_SILENCE = 0.35


def select_section(notes: list[Note], target: float = 45, step: float = 1.0) -> dict:
    total = max(n.end for n in notes)
    target = min(target, total)
    best = None
    t = 0.0
    while t + target <= total + 1e-9:
        f = window_features(notes, t, t + target)
        if f["silence_ratio"] <= MAX_SILENCE:
            hook = window_features(notes, t, min(t + 3, t + target))  # accroche immédiate
            score = viral_score(f) * 0.85 + viral_score(hook) * 0.15
            if best is None or score > best[0]:
                best = (score, t, f)
        t += step
    if best is None:  # morceau très clairsemé : meilleure fenêtre malgré tout
        f = window_features(notes, 0, target)
        best = (viral_score(f), 0.0, f)
    score, start, f = best
    reasons = []
    if f["density"] >= 4: reasons.append("forte densité")
    if f["two_hands"]: reasons.append("deux mains")
    if f["pitch_span"] >= 24: reasons.append("grande étendue")
    if f["poly"] >= 4: reasons.append("accords")
    return {"start": round(start, 1), "end": round(start + target, 1), "duration": round(target, 1),
            "score": round(score), "density": round(f["density"], 2), "reason": " + ".join(reasons) or "meilleure fenêtre disponible"}
