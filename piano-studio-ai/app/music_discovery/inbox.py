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


def watched_dirs(s) -> list[Path]:
    """Dossiers à surveiller en plus de data/inbox (réglage `inbox.watch`, ex. ~/Desktop/MIDI). Les originaux ne sont ni déplacés ni modifiés."""
    return [Path(str(d)).expanduser() for d in (s.get("inbox", {}) or {}).get("watch", []) or []]


def _key(f: Path) -> str:
    st = f.stat()
    return f"{f}|{st.st_size}|{int(st.st_mtime)}"


def _seen_file(s) -> Path:
    return folder(s) / ".seen.json"


def _seen(s) -> dict:
    try:
        return json.loads(_seen_file(s).read_text())
    except Exception:
        return {}


def watched_pending(s) -> list[Path]:
    seen, out = _seen(s), []
    for d in watched_dirs(s):
        if d.is_dir():
            out += [f for f in sorted(d.rglob("*")) if f.is_file() and f.suffix.lower() in EXT and not f.name.startswith(".") and _key(f) not in seen]
    return out


def waiting(s) -> int:
    return len(pending(s)) + len(watched_pending(s))


LAST_CHECK = {"at": 0.0}        # dernière vérification des dossiers (secondes depuis 1970), affichée dans la page


def status(s) -> dict:
    return {"path": str(folder(s)), "waiting": waiting(s), "rights": rights_confirmed(s), "last_check": LAST_CHECK["at"],
            "watch": [str(d) for d in watched_dirs(s)],
            "folders": [{"path": str(d), "exists": d.is_dir(),
                         "files": len([f for f in d.rglob("*") if f.is_file() and f.suffix.lower() in EXT]) if d.is_dir() else 0} for d in watched_dirs(s)],
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
    extra = watched_pending(s)
    if not files and not extra:
        return out
    if not rights_confirmed(s):
        log.warning("📥 %d fichier(s) en attente, mais les droits ne sont pas confirmés : rien n'est importé.", len(files) + len(extra))
        return [{"file": f.name, "status": "WAITING_RIGHTS"} for f in files + extra]
    if extra:
        seen = _seen(s)
        for f in extra:                                       # dossiers surveillés : on importe une COPIE, l'original reste en place
            try:
                if f.stat().st_size > MAX_BYTES:
                    raise ValueError("fichier trop gros (8 Mo max)")
                r = import_upload(s, f.name, f.read_bytes(), "", "")
                seen[_key(f)] = r["status"]
                out.append({"file": f.name, "status": r["status"]})
                log.info("📥 Lu dans %s : %s -> %s", f.parent.name, f.name, r["status"])
            except Exception as e:
                seen[_key(f)] = "ERROR"
                out.append({"file": f.name, "status": "ERROR", "detail": str(e)[:200]})
                log.warning("📥 Fichier ignoré %s : %s", f.name, e)
        _seen_file(s).write_text(json.dumps(seen, ensure_ascii=False))
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
