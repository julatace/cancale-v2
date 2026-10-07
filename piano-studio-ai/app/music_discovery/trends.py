"""Tendances du moment : classements musicaux publics par pays (Apple). Ces titres sont en général protégés par des droits d'auteur :
la liste sert à s'inspirer et à chercher une version libre de droits (surtout en classique), pas à copier un MIDI."""
import json
import urllib.request

APPLE = "https://rss.applemarketingtools.com/api/v2/{cc}/music/most-played/{n}/songs.json"
ITUNES = "https://itunes.apple.com/{cc}/rss/topsongs/limit={n}{genre}/json"
COUNTRIES = {"fr": "France", "us": "États-Unis", "gb": "Royaume-Uni", "es": "Espagne", "de": "Allemagne", "br": "Brésil", "it": "Italie"}
CLASSICAL_GENRE = "/genre=5"


class TrendsUnavailable(Exception):
    pass


def http_json(url: str, timeout=20) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "PianoStudioAI/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _parse_apple(d: dict) -> list[dict]:
    return [{"title": x.get("name", ""), "artist": x.get("artistName", "")} for x in d.get("feed", {}).get("results", []) if x.get("name")]


def _parse_itunes(d: dict) -> list[dict]:
    out = []
    for e in d.get("feed", {}).get("entry", []):
        name = (e.get("im:name") or {}).get("label", "")
        if name:
            out.append({"title": name, "artist": (e.get("im:artist") or {}).get("label", "")})
    return out


def fetch_trends(country: str = "fr", genre: str = "all", limit: int = 25, get=http_json) -> list[dict]:
    cc = country if country in COUNTRIES else "fr"
    attempts = []
    if genre == "classical":
        attempts.append((ITUNES.format(cc=cc, n=limit, genre=CLASSICAL_GENRE), _parse_itunes))
    else:
        attempts += [(APPLE.format(cc=cc, n=limit), _parse_apple), (ITUNES.format(cc=cc, n=limit, genre=""), _parse_itunes)]
    last = ""
    for url, parse in attempts:
        try:
            items = parse(get(url))
            if items:
                return [{"rank": i + 1, **it} for i, it in enumerate(items[:limit])]
        except Exception as e:
            last = f"{type(e).__name__}"
    raise TrendsUnavailable(f"Impossible de consulter les tendances ({last or 'aucune donnée'}). Vérifiez votre connexion.")
