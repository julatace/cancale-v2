"""Boîte de réception : un autre programme (ou toi) dépose des fichiers MIDI dans `data/inbox/`, l'agent les range dans la bibliothèque.

Formats : .mid .midi .kar. Nom conseillé « Artiste - Titre.mid » ; un fichier « même_nom.json » à côté peut donner {"title","artist"}.
Droits : rien n'est importé tant que tu n'as pas confirmé (case dans la page, ou fichier `data/inbox/.rights_confirmed`) que les fichiers
reçus sont libres de droits ou que tu as le droit de les utiliser. Les fichiers traités vont dans `done/`, les refusés dans `rejected/`."""
import json
import logging
from pathlib import Path

from app import config

log = logging.getLogger("piano.inbox")
EXT = (".mid", ".midi", ".kar")
MAX_BYTES = 8 * 1024 * 1024


def folder(s) -> Path:
    d = config.resolve(s, "data_dir") / "inbox"
    for sub in ("", "done", "rejected"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    return d


def rights_confirmed(s) -> bool:
    return (folder(s) / ".rights_confirmed").exists()


def set_rights(s, value: bool) -> None:
    f = folder(s) / ".rights_confirmed"
    if value:
        f.write_text("L'utilisateur confirme avoir les droits sur les fichiers déposés ici.\n")
    else:
        f.unlink(missing_ok=True)


def pending(s) -> list[Path]:
    return sorted(p for p in folder(s).iterdir() if p.is_file() and p.suffix.lower() in EXT)


def status(s) -> dict:
    return {"path": str(folder(s)), "waiting": len(pending(s)), "rights": rights_confirmed(s),
            "done": len([p for p in (folder(s) / "done").iterdir() if p.suffix.lower() in EXT])}


def _move(f: Path, sub: str, note: str = "") -> None:
    dest = f.parent / sub / f.name
    n = 1
    while dest.exists():
        dest = f.parent / sub / f"{f.stem}_{n}{f.suffix}"
        n += 1
    f.rename(dest)
    side = f.with_suffix(".json")
    if side.exists():
        side.rename(dest.with_suffix(".json"))
    if note:
        dest.with_suffix(".txt").write_text(note + "\n")


def scan(s, import_upload) -> list[dict]:
    """Importe chaque fichier en attente. `import_upload(s, name, data, title, artist)` fait la validation et l'inscription en base."""
    out = []
    files = pending(s)
    if not files:
        return out
    if not rights_confirmed(s):
        log.warning("📥 %d fichier(s) dans la boîte de réception, mais les droits ne sont pas confirmés : rien n'est importé.", len(files))
        return [{"file": f.name, "status": "WAITING_RIGHTS"} for f in files]
    for f in files:
        try:
            if f.stat().st_size > MAX_BYTES:
                raise ValueError("fichier trop gros (8 Mo max)")
            meta = {}
            side = f.with_suffix(".json")
            if side.exists():
                meta = json.loads(side.read_text() or "{}")
            r = import_upload(s, f.name, f.read_bytes(), str(meta.get("title", ""))[:80], str(meta.get("artist", ""))[:60])
            ok = r["status"] in ("LEGAL_CONFIRMED", "DUPLICATE")
            _move(f, "done" if ok else "rejected", "" if ok else f"refusé : {r['status']}")
            out.append({"file": f.name, "status": r["status"]})
            log.info("📥 Reçu : %s -> %s", f.name, r["status"])
        except Exception as e:
            _move(f, "rejected", f"erreur : {e}")
            out.append({"file": f.name, "status": "ERROR", "detail": str(e)[:200]})
            log.warning("📥 Fichier refusé %s : %s", f.name, e)
    return out
