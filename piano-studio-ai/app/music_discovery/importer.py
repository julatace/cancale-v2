"""Import de MIDI : n'accorde LEGAL_CONFIRMED que sur déclaration explicite d'une source autorisée."""
import shutil
from pathlib import Path

from app.database import db
from app.midi_analyzer.parser import MidiError, parse_midi

ALLOWED = {"user_owned", "public_domain", "licensed"}


def classify(source: str, license_proof: str | None, allowed=ALLOWED) -> str:
    if source in allowed and license_proof and license_proof.strip():
        return "LEGAL_CONFIRMED"
    if source in allowed:
        return "LICENSE_REVIEW"  # source plausible mais sans preuve de licence
    return "UNKNOWN"


def import_midi(conn, path, title, artist, source, license_proof=None, dest_dir=None, allowed=ALLOWED) -> dict:
    path = Path(path)
    try:
        notes, _ = parse_midi(path)
        if not notes:
            raise MidiError("aucune note")
    except (MidiError, IndexError, OSError) as e:
        db.log_error(conn, "midi_import", f"{path.name}: {e}")
        return {"status": "REJECTED", "reason": f"MIDI invalide: {e}", "song_id": None}
    digest = db.sha256_file(path)
    dup = conn.execute("SELECT id FROM songs WHERE hash=?", (digest,)).fetchone()
    if dup:
        return {"status": "DUPLICATE", "reason": "même MIDI déjà importé", "song_id": dup["id"]}
    status = classify(source, license_proof, allowed)
    stored = path
    if dest_dir and status == "LEGAL_CONFIRMED":
        Path(dest_dir).mkdir(parents=True, exist_ok=True)
        stored = Path(dest_dir) / f"{digest[:16]}.mid"
        shutil.copy2(path, stored)
    sid = db.add_song(conn, title, artist, f"{source}: {license_proof or ''}".strip(": "), status, stored, digest)
    return {"status": status, "reason": "ok" if status == "LEGAL_CONFIRMED" else "SKIP SONG", "song_id": sid}


def candidate_score(c: dict, weights: dict, penalties: float = 0) -> float:
    """TOTAL SCORE du §5 (entrées 0-100), moins pénalités."""
    keys = {"trend": "trend", "piano": "piano", "short_video": "short_video",
            "difficulty": "difficulty", "visual": "visual", "novelty": "novelty"}
    return round(sum(c.get(k, 0) * weights[w] for k, w in keys.items()) - penalties, 1)
