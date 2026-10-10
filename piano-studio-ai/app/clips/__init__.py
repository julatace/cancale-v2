"""Agent « clips » : publie des vidéos DÉJÀ PRÊTES (tu les déposes dans un dossier), sans rien fabriquer.
Il en tire le titre (nom du fichier, ou fichier .txt du même nom), la description et les hashtags, puis envoie chaque vidéo à TikTok et YouTube,
programmée à la date de l'agenda, depuis SON propre profil Chrome. Une vidéo publiée est supprimée du Mac. Pas de doublon (empreinte du fichier)."""
import hashlib
import json
import logging
import re
import shutil
import subprocess
import time
from pathlib import Path

from app import config
from app.database import db

log = logging.getLogger("piano.clips")
EXT = (".mp4", ".mov", ".m4v")
GOOD = ("PUBLISHED", "DRAFT", "SCHEDULED")
BLOCKING = ("SENDING", "UNCERTAIN")                 # envoi peut-être déjà parti : jamais renvoyé tout seul


def conf(s) -> dict:
    return {"folder": "~/Desktop/Clips", "description": "", "hashtags": "#fyp #pourtoi", "consume": True,
            "shorts_max_seconds": 180, **(s.get("clips") or {})}


def is_clips(s) -> bool:
    return (s.get("agent") or {}).get("kind") == "clips"


def folder(s) -> Path:
    return Path(conf(s)["folder"]).expanduser()


def title_from_name(name: str) -> str:
    """« 01_mon_super_clip.mp4 » -> « Mon super clip »."""
    t = re.sub(r"\.[A-Za-z0-9]+$", "", name)
    t = re.sub(r"^\s*\d{1,3}\s*[-_.)]\s*", "", t)          # numéro d'ordre au début
    t = re.sub(r"[_]+", " ", t).strip(" -")
    t = re.sub(r"\s+", " ", t)
    return (t[:1].upper() + t[1:]) if t else "Vidéo"


def sidecar(f: Path):
    """Fichier texte du même nom : 1re ligne = titre ; une ligne qui ne contient que des #hashtags = hashtags de CETTE vidéo ; le reste = description.
    Retourne (titre, description, hashtags)."""
    t = f.with_suffix(".txt")
    if not t.exists():
        return None, None, None
    lines = [x.rstrip() for x in t.read_text(encoding="utf-8", errors="ignore").splitlines()]
    nonempty = [x for x in lines if x.strip()]
    if not nonempty:
        return None, None, None
    title, rest = nonempty[0].strip()[:95], []
    tags = None
    for x in lines[lines.index(nonempty[0]) + 1:]:
        if x.strip() and all(w.startswith("#") for w in x.split()):
            tags = [w for w in x.split()][:8]
        else:
            rest.append(x)
    desc = "\n".join(rest).strip()
    return title or None, desc or None, tags


def probe(f: Path) -> dict:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,codec_name:format=duration",
                        "-of", "json", str(f)], capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
        st = d["streams"][0]
        return {"width": int(st["width"]), "height": int(st["height"]), "duration": float(d["format"]["duration"])}
    except Exception:
        raise ValueError("vidéo illisible")


def settled(f: Path, wait: float = 4.0) -> bool:
    """Le fichier ne grossit plus (copie terminée) : on n'importe jamais une vidéo à moitié copiée."""
    try:
        a = f.stat()
        if time.time() - a.st_mtime < wait:
            return False
        return a.st_size > 0
    except OSError:
        return False


def pending(s) -> list[Path]:
    d = folder(s)
    if not d.is_dir():
        return []
    return sorted((f for f in d.iterdir() if f.is_file() and f.suffix.lower() in EXT and not f.name.startswith(".")), key=lambda f: f.stat().st_mtime)


def file_hash(f: Path) -> str:
    h = hashlib.sha256()
    with open(f, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_content(s, title: str, description: str | None, vertical: bool, duration: float, hashtags: list | None = None) -> dict:
    c = conf(s)
    tags = hashtags or [t for t in re.split(r"\s+", c["hashtags"].strip()) if t.startswith("#")][:8]
    desc = (description or c["description"] or "").strip()
    body = (desc + "\n\n" if desc else "") + " ".join(tags)
    return {"title": title, "description": body.strip(), "hashtags": tags, "youtube_title": title,
            "tiktok_caption": f"{title} " + " ".join(tags), "instagram_caption": f"{title}\n" + " ".join(tags),
            "pinned_comment": "", "shorts": bool(vertical and duration <= c["shorts_max_seconds"]), "format": "vertical" if vertical else "horizontal"}


def import_pending(s, conn) -> list[dict]:
    """Prend en charge les nouvelles vidéos du dossier (déplacées dans l'espace de travail de l'agent). Doublons et fichiers illisibles : écartés."""
    out = []
    work = config.resolve(s, "data_dir") / "rendered"
    work.mkdir(parents=True, exist_ok=True)
    c = conf(s)
    for f in pending(s):
        if not settled(f):
            continue
        try:
            info = probe(f)
        except ValueError:
            log.warning("clips : « %s » illisible, ignorée", f.name)
            out.append({"file": f.name, "status": "UNREADABLE"})
            _quarantine(f)
            continue
        h = file_hash(f)
        if conn.execute("SELECT 1 FROM videos WHERE video_hash=?", (h,)).fetchone():
            log.info("clips : « %s » déjà prise en charge (doublon), écartée", f.name)
            out.append({"file": f.name, "status": "DUPLICATE"})
            _quarantine(f, "doublons")
            continue
        t_side, d_side, tags_side = sidecar(f)
        title = t_side or title_from_name(f.name)
        vertical = info["height"] >= info["width"]
        content = build_content(s, title, d_side, vertical, info["duration"], tags_side)
        dest = work / f"{h[:10]}{f.suffix.lower()}"
        (shutil.move if c["consume"] else shutil.copy2)(str(f), str(dest))
        if c["consume"]:
            f.with_suffix(".txt").unlink(missing_ok=True)
        fmt = content["format"]
        conn.execute("INSERT INTO videos(style,duration,output_path,quality_score,status,video_hash,title,meta,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                     (f"clips|{fmt}", info["duration"], str(dest), 100, "READY", h, title, json.dumps(content, ensure_ascii=False), db.now()))
        conn.commit()
        log.info("clips : « %s » prise en charge (%s, %.0f s)", title, fmt, info["duration"])
        out.append({"file": f.name, "status": "IMPORTED", "title": title})
    return out


def import_file(s, conn, f, title=None, description=None, hashtags=None) -> int:
    """Prend en charge UN fichier précis (commande `post`). Copié dans l'espace de travail : l'original n'est pas touché.
    Même contenu déjà pris en charge : on réutilise cette vidéo (jamais de doublon) ; déjà publiée : erreur claire."""
    f = Path(f).expanduser()
    if not f.is_file() or f.suffix.lower() not in EXT:
        raise ValueError(f"fichier vidéo introuvable ou format non géré (.mp4 / .mov) : {f}")
    info = probe(f)
    h = file_hash(f)
    row = conn.execute("SELECT id FROM videos WHERE video_hash=?", (h,)).fetchone()
    if row:
        st = {x["status"] for x in conn.execute("SELECT status FROM publications WHERE video_id=?", (row["id"],))}
        if st & set(GOOD):
            raise ValueError("cette vidéo a déjà été envoyée (même contenu) : rien n'est renvoyé")
        if st & set(BLOCKING):
            raise ValueError("un envoi de cette vidéo est peut-être déjà parti : vérifie dans TikTok / YouTube avant de recommencer")
        return row["id"]
    t_side, d_side, tags_side = sidecar(f)
    title = (title or t_side or title_from_name(f.name))[:95]
    vertical = info["height"] >= info["width"]
    content = build_content(s, title, description or d_side, vertical, info["duration"], hashtags or tags_side)
    work = config.resolve(s, "data_dir") / "rendered"
    work.mkdir(parents=True, exist_ok=True)
    dest = work / f"{h[:10]}{f.suffix.lower()}"
    shutil.copy2(str(f), str(dest))
    cur = conn.execute("INSERT INTO videos(style,duration,output_path,quality_score,status,video_hash,title,meta,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                       (f"clips|{content['format']}", info["duration"], str(dest), 100, "READY", h, title, json.dumps(content, ensure_ascii=False), db.now()))
    conn.commit()
    return cur.lastrowid


def _quarantine(f: Path, sub: str = "ignorées"):
    d = f.parent / sub
    d.mkdir(exist_ok=True)
    try:
        shutil.move(str(f), str(d / f.name))
    except OSError:
        pass


def queue_ids(conn) -> list[int]:
    """Vidéos prêtes à partir, de la plus ancienne à la plus récente, sans envoi en cours ni déjà parti."""
    ids = []
    for r in conn.execute("SELECT id, output_path FROM videos WHERE style LIKE 'clips|%' AND status='READY' ORDER BY id"):
        if not r["output_path"] or not Path(r["output_path"]).exists():
            continue
        st = {x["status"] for x in conn.execute("SELECT status FROM publications WHERE video_id=?", (r["id"],))}
        if st & set(BLOCKING) or (st and st <= set(GOOD)):
            continue
        ids.append(r["id"])
    return ids


def available(s, conn) -> int:
    """Vidéos que l'agent peut encore publier (déjà prises en charge + celles qui attendent dans le dossier)."""
    return len(queue_ids(conn)) + len(pending(s))


def run_one(s, seed=None, dry_run=False, publish=True, level=None, fmt=None, formats=None, song_id=None, lang=None) -> dict:
    """Remplace la fabrication d'une vidéo : prend en charge le dossier, puis fournit la prochaine vidéo prête (même forme de résultat que le piano)."""
    conn = db.connect(config.resolve(s, "database"))
    import_pending(s, conn)
    ids = queue_ids(conn)
    if not ids:
        raise RuntimeError("Plus aucun morceau : dépose des vidéos dans le dossier de l'agent")
    r = conn.execute("SELECT id, title, style, duration FROM videos WHERE id=?", (ids[0],)).fetchone()
    f = (r["style"] or "").partition("|")[2]
    return {"status": "READY", "video_id": r["id"], "title": r["title"], "format": f, "engine": "clips", "duration": r["duration"],
            "qc": {"score": 100, "issues": []}, "videos": [{"status": "READY", "video_id": r["id"], "title": r["title"], "format": f, "engine": "clips"}]}
