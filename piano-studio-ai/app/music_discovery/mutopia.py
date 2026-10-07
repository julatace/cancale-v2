"""Recherche de MIDI sur Mutopia Project (pièces classiques pour piano, licence indiquée sur chaque page).
Seuls Public Domain / CC0 / CC-BY sont acceptés ; tout le reste est ignoré (SKIP SONG).
NB : le HTML du site n'a pas pu être vérifié depuis le conteneur de développement -> `piano fetch-midi --debug`."""
import html
import random
import re
import urllib.request
from urllib.parse import urljoin

BASE = "https://www.mutopiaproject.org/"
LIST_URL = BASE + "cgibin/make-table.cgi?Instrument=Piano&solo=1&startat={start}&searchingfor="
OK_LICENSES = [("Public Domain", re.compile(r"Public Domain", re.I)),
               ("CC0", re.compile(r"CC0|Creative Commons Zero|Public Domain Dedication", re.I)),
               ("CC-BY", re.compile(r"Creative Commons Attribution(?!-)(?!.*(?:Share|NonCommercial|NoDerivs))", re.I))]
BAD = re.compile(r"ShareAlike|NonCommercial|NoDerivs|Share Alike", re.I)


def http_get(url: str, timeout=30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "PianoStudioAI/0.1 (+personal use)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def list_pieces(page_html: str) -> list[str]:
    return sorted(set(urljoin(BASE + "cgibin/", m) for m in re.findall(r'href="([^"]*piece-info\.cgi\?id=\d+[^"]*)"', page_html)))


def parse_piece(page_html: str, url: str) -> dict | None:
    """Retourne {title, composer, midi_url, license, credit} ou None si licence non autorisée / pas de MIDI."""
    mids = re.findall(r'href="([^"]+\.mid)"', page_html, re.I)
    if not mids:
        return None
    text = html.unescape(re.sub(r"<[^>]+>", " ", page_html))
    if BAD.search(text):
        return None
    lic = next((n for n, rx in OK_LICENSES if rx.search(text)), None)
    if not lic:
        return None
    t = re.search(r"<title>(.*?)</title>", page_html, re.S | re.I)
    title = html.unescape(t.group(1)).split("|")[0].split(" - ")[0].strip() if t else "Piece"
    composer = ""
    if " by " in title:                                   # « Consolation, S.172 No.1, by F. Liszt (1811–1886) »
        title, composer = title.rsplit(" by ", 1)
        composer = re.sub(r"\s*\(.*?\)\s*", "", composer).strip()
    if not composer:
        comp = re.search(r"Composer[^A-Za-z]{0,40}([A-Z][^\n<]{2,40})", text)
        composer = comp.group(1).strip() if comp else "Unknown"
    title = title.strip(" ,")
    return {"title": title[:80], "composer": composer[:40],
            "midi_url": urljoin(url, mids[0]), "license": lic,
            "credit": "Mutopia Project (CC BY)" if lic == "CC-BY" else ""}


def fetch_one(get=http_get, rnd=None, tried=None, debug=print):
    """Choisit une pièce au hasard parmi les pages de liste ; retourne (infos, bytes MIDI) ou None."""
    rnd = rnd or random.Random()
    tried = tried or set()
    for _ in range(3):
        page = get(LIST_URL.format(start=rnd.randrange(0, 600, 10)))
        pieces = [u for u in list_pieces(page) if u not in tried]
        debug(f"[mutopia] {len(pieces)} pièces trouvées sur la page de liste")
        rnd.shuffle(pieces)
        for url in pieces[:8]:
            tried.add(url)
            info = parse_piece(get(url), url)
            if not info:
                debug(f"[mutopia] ignorée (licence/MIDI) : {url}")
                continue
            data = _bytes(info["midi_url"], get)
            if data[:4] == b"MThd":
                info["page"] = url
                return info, data
    return None


def _bytes(url, get):
    if get is http_get:
        req = urllib.request.Request(url, headers={"User-Agent": "PianoStudioAI/0.1"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    v = get(url)
    return v if isinstance(v, bytes) else v.encode("latin-1")
