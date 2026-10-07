"""Réduction d'un arrangement de groupe (fichier karaoké, multi-pistes) en arrangement de PIANO lisible :
mélodie (main droite) + basse (main gauche) + éventuellement un accompagnement. Batterie exclue (déjà retirée à la lecture)."""
import re
from collections import defaultdict

MELODY_NAMES = re.compile(r"chant|vocal|voice|voix|lead|melod|mélod|sing|lyric|vox", re.I)
BASS_NAMES = re.compile(r"bass|basse|contrebasse", re.I)
CHORD_NAMES = re.compile(r"piano|keys|clav|organ|orgue|guit|gt$|gtr|synth|accord|harp", re.I)
SKIP_NAMES = re.compile(r"drum|batt|perc|rev|fx|effect|sfx|choeur|choir|choral", re.I)


def _stats(notes):
    by = defaultdict(list)
    for n in notes:
        by[n.track].append(n)
    out = {}
    for t, ns in by.items():
        onsets = len({round(n.start, 2) for n in ns})
        out[t] = {"count": len(ns), "mean": sum(n.pitch for n in ns) / len(ns), "poly": len(ns) / max(onsets, 1)}
    return by, out


def pick_tracks(notes, info=None, max_tracks: int = 3, max_density: float = 9.0) -> list[int]:
    """Choisit les pistes à garder : mélodie, basse, accompagnement."""
    info = info or {}
    by, st = _stats(notes)
    if len(by) <= 2:
        return list(by)
    biggest = max(s["count"] for s in st.values())
    usable = {t: s for t, s in st.items() if s["count"] >= max(40, 0.04 * biggest) and not SKIP_NAMES.search(info.get(t, {}).get("name", ""))}
    if not usable:
        return list(by)
    chosen = []
    # mélodie : piste de paroles (karaoké) > nom explicite > piste la plus « monophonique » et aiguë
    lyrics = [t for t in usable if info.get(t, {}).get("texts", 0) > 50]
    named = [t for t in usable if MELODY_NAMES.search(info.get(t, {}).get("name", ""))]
    if lyrics:
        melody = max(lyrics, key=lambda t: info[t]["texts"])
    elif named:
        melody = max(named, key=lambda t: usable[t]["count"])
    else:
        mono = [t for t, s in usable.items() if s["poly"] < 1.4 and s["mean"] >= 58] or list(usable)
        melody = max(mono, key=lambda t: (usable[t]["mean"] / 100) + min(usable[t]["count"], 800) / 2000)
    chosen.append(melody)
    rest = {t: s for t, s in usable.items() if t != melody}
    bass_named = [t for t in rest if BASS_NAMES.search(info.get(t, {}).get("name", ""))]
    bass = bass_named[0] if bass_named else (min(rest, key=lambda t: rest[t]["mean"]) if rest and min(s["mean"] for s in rest.values()) < 52 else None)
    if bass is not None:
        chosen.append(bass)
        rest.pop(bass, None)
    dur = max(n.end for n in notes) or 1.0
    used = sum(st[t]["count"] for t in chosen)
    chords = {t: s for t, s in rest.items() if CHORD_NAMES.search(info.get(t, {}).get("name", ""))
              and (used + s["count"]) / dur <= max_density}                      # l'accompagnement ne doit pas rendre le morceau illisible
    if chords and len(chosen) < max_tracks:
        # accompagnement : la piste d'accords la plus « verticale » (plusieurs notes à la fois), sinon la moins chargée
        chosen.append(max(chords, key=lambda t: (chords[t]["poly"], -chords[t]["count"])))
    return chosen


def arrange_for_piano(notes, info=None, max_tracks: int = 3, max_density: float = 9.0):
    keep = set(pick_tracks(notes, info, max_tracks, max_density))
    return [n for n in notes if n.track in keep]
