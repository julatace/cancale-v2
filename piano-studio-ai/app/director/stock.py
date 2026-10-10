"""Réserve de morceaux : l'agent télécharge et vérifie des MIDI libres de droits EN AVANCE, pour ne jamais attendre au clic."""
import logging
import random
import threading
from pathlib import Path

from app import config
from app.database import db
from app.music_discovery import importer, mutopia

log = logging.getLogger("piano.stock")
_LOCK = threading.Lock()


def usable_ids(conn, s) -> list[int]:
    rows = conn.execute("SELECT id, midi_path FROM songs WHERE license='LEGAL_CONFIRMED' ORDER BY id").fetchall()
    return [r["id"] for r in rows if r["midi_path"] and Path(r["midi_path"]).exists()
            and db.song_usable(conn, r["id"], s["same_song_cooldown_days"])[0]]


def count(s) -> int:
    return len(usable_ids(db.connect(config.resolve(s, "database")), s))


def ensure_stock(s, target: int | None = None, fetch=None, rnd=None) -> dict:
    """Complète la réserve jusqu'à `target` morceaux utilisables. Sans danger si hors-ligne (aucune exception)."""
    target = target if target is not None else s.get("stock", {}).get("target", 3)
    fetch = fetch or mutopia.fetch_one
    if not _LOCK.acquire(blocking=False):
        return {"skipped": "déjà en cours"}
    try:
        conn = db.connect(config.resolve(s, "database"))
        before = len(usable_ids(conn, s))
        added, tries = 0, 0
        midi_dir = config.resolve(s, "data_dir") / "midi"
        midi_dir.mkdir(parents=True, exist_ok=True)
        rnd = rnd or random.Random()
        while before + added < target and tries < target * 4 and s.get("midi_sources", {}).get("mutopia", False):
            tries += 1
            try:
                res = fetch(rnd=rnd, debug=lambda *_: None)
                if not res:
                    continue
                info, data = res
                f = midi_dir / f"stock_{rnd.randrange(10**9)}.mid"
                f.write_bytes(data)
                r = importer.import_midi(conn, f, info["title"], info["composer"], "public_domain",
                                         f"Mutopia {info['license']} {info['page']}", dest_dir=midi_dir)
                f.unlink(missing_ok=True)
                if r["status"] == "LEGAL_CONFIRMED":
                    added += 1
                    log.info("📦 Morceau mis en réserve : %s - %s", info["title"], info["composer"])
            except Exception as e:             # hors-ligne, site changé... : on réessaiera plus tard
                db.log_error(conn, "stock", f"{type(e).__name__}: {str(e)[:150]}", "WARNING")
                break
        return {"before": before, "added": added, "after": before + added, "target": target}
    finally:
        _LOCK.release()


def refill_in_background(s) -> threading.Thread:
    if s.get("songs", {}).get("only_mine", False) or (s.get("agent") or {}).get("kind") == "clips":    # on ne télécharge rien : seuls tes morceaux / tes vidéos servent
        t = threading.Thread(target=lambda: None, daemon=True); t.start(); return t
    t = threading.Thread(target=lambda: ensure_stock(s), daemon=True, name="stock-refill")
    t.start()
    return t
