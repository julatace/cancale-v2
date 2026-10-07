"""Recherche d'un morceau par son titre : bibliothèque locale puis MIDI libres de droits (Mutopia). Dit honnêtement s'il n'y a rien."""
import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app import config
from app.database import db
from app.music_discovery import importer, mutopia

SEARCH_URL = mutopia.BASE + "cgibin/make-table.cgi?searchingfor={q}&startat=0"
ALLOWED_PREFIX = mutopia.BASE                                   # on ne télécharge que depuis ce site (pas de lien arbitraire)
NOT_FOUND = ("Aucun MIDI libre de droits trouvé pour « {q} ». Les chansons récentes sont protégées par des droits d'auteur : "
             "si vous avez le fichier MIDI et le droit de l'utiliser, ajoutez-le dans « Mes morceaux ».")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower().replace("-", " "))


def search_local(conn, q: str) -> list[dict]:
    words = _norm(q).split()
    out = []
    for r in conn.execute("SELECT id,title,artist,source,midi_path FROM songs WHERE license='LEGAL_CONFIRMED' ORDER BY id DESC"):
        text = _norm(f"{r['title']} {r['artist']}")
        if words and all(w in text for w in words) and r["midi_path"] and Path(r["midi_path"]).exists():
            out.append({"kind": "library", "song_id": r["id"], "title": r["title"], "composer": r["artist"] or ""})
    return out


def search_mutopia(q: str, get=mutopia.http_get, limit: int = 6) -> list[dict]:
    """Pièces Mutopia correspondant à la recherche, dont la licence est acceptée ET qui ont un fichier MIDI."""
    page = get(SEARCH_URL.format(q=urllib.parse.quote_plus(q)))
    urls = mutopia.list_pieces(page)[: limit + 4]

    def one(u):
        try:
            info = mutopia.parse_piece(get(u), u)
        except Exception:
            return None
        return {**info, "kind": "online", "page": u} if info else None

    with ThreadPoolExecutor(max_workers=6) as ex:
        found = [r for r in ex.map(one, urls) if r]
    return found[:limit]


def search(s: dict, q: str, get=mutopia.http_get) -> dict:
    q = (q or "").strip()
    if len(q) < 2:
        return {"query": q, "results": [], "message": "Tapez au moins 2 lettres."}
    conn = db.connect(config.resolve(s, "database"))
    results = search_local(conn, q)
    online_error = ""
    try:
        have = {_norm(r["title"]) for r in results}
        results += [r for r in search_mutopia(q, get) if _norm(r["title"]) not in have]
    except Exception as e:
        online_error = f"Recherche en ligne impossible ({type(e).__name__}). Vérifiez votre connexion."
    msg = "" if results else (online_error or NOT_FOUND.format(q=q))
    if results and online_error:
        msg = online_error
    return {"query": q, "results": results, "message": msg}


def import_found(s: dict, page_url: str, get=mutopia.http_get) -> dict:
    """Télécharge le MIDI d'une pièce Mutopia trouvée par la recherche et l'ajoute à la bibliothèque (licence déjà vérifiée)."""
    if not page_url.startswith(ALLOWED_PREFIX):
        raise ValueError("adresse non autorisée")
    info = mutopia.parse_piece(get(page_url), page_url)
    if not info:
        raise ValueError("licence non autorisée ou MIDI introuvable")
    data = mutopia._bytes(info["midi_url"], get)
    if data[:4] != b"MThd":
        raise ValueError("fichier MIDI invalide")
    midi_dir = config.resolve(s, "data_dir") / "midi"
    midi_dir.mkdir(parents=True, exist_ok=True)
    tmp = midi_dir / "search_tmp.mid"
    tmp.write_bytes(data)
    try:
        conn = db.connect(config.resolve(s, "database"))
        r = importer.import_midi(conn, tmp, info["title"], info["composer"], "public_domain",
                                 f"Mutopia {info['license']} {page_url}", dest_dir=midi_dir)
    finally:
        tmp.unlink(missing_ok=True)
    return {"status": r["status"], "song_id": r.get("song_id"), "title": info["title"], "license": info["license"]}


# ---------- sélection à parcourir ----------
POPULAR = [  # (titre affiché, compositeur, mots de recherche) : classiques du domaine public très écoutés
    ("Clair de Lune", "Debussy", "clair de lune"), ("Für Elise", "Beethoven", "fur elise"),
    ("Gymnopédie No. 1", "Satie", "gymnopedie"), ("Nocturne Op. 9 No. 2", "Chopin", "nocturne op 9"),
    ("Prélude en Do majeur", "Bach", "prelude c major"), ("Sonate « Clair de Lune »", "Beethoven", "moonlight sonata"),
    ("Valse minute", "Chopin", "minute waltz"), ("Rêverie", "Debussy", "reverie"),
    ("Canon en Ré", "Pachelbel", "canon"), ("Gnossienne No. 1", "Satie", "gnossienne"),
    ("Rondo alla Turca", "Mozart", "rondo alla turca"), ("La Campanella", "Liszt", "campanella"),
    ("Arabesque No. 1", "Debussy", "arabesque"), ("Ode à la joie", "Beethoven", "ode to joy"),
]
LATEST_URLS = [mutopia.BASE + "latestadditions.html"]
_LATEST_CACHE: dict = {"at": 0.0, "data": None}


def _piece_id(url: str) -> int:
    m = re.search(r"id=(\d+)", url)
    return int(m.group(1)) if m else 0


def latest(get=mutopia.http_get, limit: int = 10, ttl: float = 1800.0) -> dict:
    """Derniers morceaux ajoutés au catalogue libre de droits (les identifiants les plus élevés sont les plus récents)."""
    import time
    if _LATEST_CACHE["data"] and time.time() - _LATEST_CACHE["at"] < ttl and get is mutopia.http_get:
        return _LATEST_CACHE["data"]
    urls, err = [], ""
    for src in LATEST_URLS:
        try:
            urls = mutopia.list_pieces(get(src))
            if urls:
                break
        except Exception as e:
            err = f"{type(e).__name__}"
    if not urls:
        return {"results": [], "message": "Impossible de consulter les nouveautés" + (f" ({err})" if err else "") + ". Vérifiez votre connexion."}
    urls = sorted(urls, key=_piece_id, reverse=True)[: limit * 2]

    def one(u):
        try:
            info = mutopia.parse_piece(get(u), u)
        except Exception:
            return None
        return {**info, "kind": "online", "page": u, "id": _piece_id(u)} if info else None

    with ThreadPoolExecutor(max_workers=6) as ex:
        found = [r for r in ex.map(one, urls) if r]
    found.sort(key=lambda r: r["id"], reverse=True)
    out = {"results": found[:limit], "message": "" if found else "Aucune nouveauté exploitable (licence ou MIDI manquant)."}
    if found and get is mutopia.http_get:
        _LATEST_CACHE.update(at=time.time(), data=out)
    return out


def popular() -> list[dict]:
    return [{"title": t, "composer": c, "query": q} for t, c, q in POPULAR]
