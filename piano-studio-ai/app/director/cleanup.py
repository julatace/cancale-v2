"""Libère le disque : une vidéo publiée partout où elle devait l'être est supprimée (fichier, miniature, copie de secours)."""
import logging
import shutil
from pathlib import Path

from app import config

log = logging.getLogger("piano.cleanup")
GOOD = ("PUBLISHED", "DRAFT")


def enabled(s) -> bool:
    return bool(s.get("storage", {}).get("delete_after_publish", True))


def all_published(results) -> bool:
    """Vrai seulement si chaque plateforme réelle (hors dossier de secours) a bien publié : un échec garde la vidéo pour un nouvel essai."""
    real = [r for r in results if r.get("platform") != "outbox"]
    return bool(real) and all(r.get("status") in GOOD for r in real)


def delete_after_publish(s, conn, video_id: int, results) -> list[str]:
    """Supprime les fichiers de la vidéo si tout est publié. Garde la ligne en base (titre, date, plateformes) pour l'historique."""
    if not enabled(s) or not all_published(results):
        return []
    row = conn.execute("SELECT output_path FROM videos WHERE id=?", (int(video_id),)).fetchone()
    removed = []
    if row and row["output_path"]:
        mp4 = Path(row["output_path"])
        for f in (mp4, mp4.with_suffix(".jpg")):                          # vidéo + miniature
            if f.exists():
                try:
                    f.unlink()
                    removed.append(f.name)
                except OSError as e:
                    log.warning("suppression impossible (%s) : %s", f.name, e)
    try:
        box = config.resolve(s, "data_dir") / "published" / str(video_id)    # copie de secours (dossier « prêt à poster »)
    except KeyError:
        box = None
    if box is not None and box.is_dir():
        shutil.rmtree(box, ignore_errors=True)
        removed.append(f"published/{video_id}")
    if removed:
        conn.execute("UPDATE videos SET output_path='' WHERE id=?", (int(video_id),))
        conn.commit()
        log.info("🧹 Vidéo publiée : fichiers supprimés pour libérer de la place (%s)", ", ".join(removed))
    return removed


def purge_published(s, conn) -> int:
    """Rattrapage : supprime les fichiers des vidéos déjà publiées (statut PUBLISHED) restés sur le disque."""
    n = 0
    for r in conn.execute("SELECT id FROM videos WHERE status='PUBLISHED' AND output_path!=''").fetchall():
        n += len(delete_after_publish(s, conn, r["id"], [{"platform": "x", "status": "PUBLISHED"}]))
    return n
