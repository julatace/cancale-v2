"""Audit de la qualité des fichiers MIDI d'un dossier : dit, pour chaque fichier, s'il donnera une BONNE vidéo (piano / balle qui rebondit) et pourquoi."""
from pathlib import Path

from .analyzer import analyze
from .arrange import arrange_for_piano
from .parser import parse_midi, parse_midi_info

EXT = (".mid", ".midi", ".kar")


def _melody_clarity(notes) -> float:
    """0-1 : part des moments où une ligne mélodique claire se détache (une attaque nette, pas un nuage de notes simultanées)."""
    if not notes:
        return 0.0
    ons = sorted(n.start for n in notes)
    groups, last = 0, -9.0
    for t in ons:
        if t - last > 0.05:
            groups += 1
        last = t
    return min(1.0, groups / max(len(ons) * 0.55, 1))


def audit_file(path) -> dict:
    p = Path(path)
    r = {"file": p.name, "score": 0, "verdict": "à éviter", "issues": [], "notes": 0, "duration": 0.0, "tracks": 0, "bpm": 0.0}
    try:
        notes, tempo = parse_midi(p)
    except Exception as e:
        r["issues"].append(f"illisible ({type(e).__name__})")
        return r
    if not notes:
        r["issues"].append("aucune note de piano (fichier vide ou seulement de la batterie)")
        return r
    r["tracks"] = len({n.track for n in notes})
    try:
        notes = arrange_for_piano(notes, parse_midi_info(p))
    except Exception:
        pass
    first = min(n.start for n in notes)
    a = analyze(notes, tempo)
    dur = a["duration"] - (first if first > 1.5 else 0)
    r.update(notes=len(notes), duration=round(dur, 1), bpm=a["bpm"])
    score = 100
    if dur < 20:
        score -= 45
        r["issues"].append(f"trop court ({dur:.0f} s) : il faut au moins ~20 s pour une vidéo")
    elif dur < 35:
        score -= 15
        r["issues"].append(f"assez court ({dur:.0f} s) : vidéo courte")
    if len(notes) < 40:
        score -= 30
        r["issues"].append(f"trop peu de notes ({len(notes)})")
    dens = len(notes) / max(dur, 1)
    if dens > 14:
        score -= 20
        r["issues"].append(f"très dense ({dens:.0f} notes/s) : difficile à suivre")
    elif dens < 0.8:
        score -= 20
        r["issues"].append(f"très peu de notes ({dens:.1f}/s) : vidéo vide")
    clar = _melody_clarity(notes)
    if clar < 0.35:
        score -= 20
        r["issues"].append("mélodie peu lisible (surtout des gros accords)")
    if first > 5:
        score -= 5
        r["issues"].append(f"long silence au début ({first:.0f} s) : coupé automatiquement")
    if r["tracks"] > 6:
        score -= 5
        r["issues"].append(f"{r['tracks']} pistes (fichier de groupe) : arrangé automatiquement pour le piano")
    r["score"] = max(score, 0)
    r["verdict"] = "très bon" if score >= 85 else "bon" if score >= 65 else "moyen" if score >= 45 else "à éviter"
    return r


def audit_folder(folder) -> list[dict]:
    d = Path(folder).expanduser()
    files = sorted(f for f in d.rglob("*") if f.is_file() and f.suffix.lower() in EXT) if d.is_dir() else []
    return sorted((audit_file(f) for f in files), key=lambda r: -r["score"])
