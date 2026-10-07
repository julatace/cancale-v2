import json
import urllib.error
import urllib.parse
import urllib.request

from .base import NotConfigured, Result, env


def _http(req: urllib.request.Request, timeout=300):
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, dict(r.headers), r.read()


def explain_http_error(e: urllib.error.HTTPError) -> str:
    """Message clair pour les erreurs YouTube les plus fréquentes."""
    try:
        err = json.loads(e.read()).get("error", {})
        reason = (err.get("errors") or [{}])[0].get("reason", "")
        msg = err.get("message", "")
    except Exception:
        reason, msg = "", ""
    if reason in ("quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"):
        return "quota quotidien YouTube atteint (environ 6 envois par jour) : réessayez demain"
    if reason in ("uploadLimitExceeded",):
        return "limite d'envois de la chaîne atteinte : réessayez plus tard"
    if reason in ("forbidden", "insufficientPermissions") or e.code == 403:
        return f"accès refusé par YouTube ({reason or 403}) : relancez `./p.sh youtube-login` et acceptez toutes les autorisations"
    if e.code == 401:
        return "autorisation YouTube expirée : relancez `./p.sh youtube-login`"
    return f"HTTP {e.code} {reason} {msg}"[:200]


class YouTube:
    platform = "youtube"

    def __init__(self, http=_http, privacy: str = "public", category: str = "10"):
        self.http, self.privacy, self.category = http, privacy, category

    def _token(self) -> str:
        body = urllib.parse.urlencode({"client_id": env("YOUTUBE_CLIENT_ID"), "client_secret": env("YOUTUBE_CLIENT_SECRET"),
                                       "refresh_token": env("YOUTUBE_REFRESH_TOKEN"), "grant_type": "refresh_token"}).encode()
        _, _, data = self.http(urllib.request.Request("https://oauth2.googleapis.com/token", data=body))
        return json.loads(data)["access_token"]

    def check(self) -> tuple[bool, str]:
        """Vérifie les clés pour de vrai (demande un jeton à Google)."""
        try:
            self._token()
            return True, "connecté"
        except NotConfigured as e:
            return False, f"variable manquante : {e}"
        except urllib.error.HTTPError as e:
            return False, "clés refusées par Google : relancez `./p.sh youtube-login`" if e.code in (400, 401) else explain_http_error(e)
        except Exception as e:
            return False, f"{type(e).__name__} (connexion internet ?)"

    @staticmethod
    def build_snippet(meta: dict, privacy: str, category: str) -> dict:
        shorts = meta.get("shorts", True)
        title = meta.get("youtube_title") or meta["title"]
        title = title[:100] if (not shorts or "#Shorts" in title) else title[:91] + " #Shorts"          # Shorts : le mot-clé aide YouTube à classer la vidéo
        desc = meta["description"] + ("\n\n#Shorts" if shorts else "")
        tags, total = [], 0
        for k in [*(meta.get("keywords") or []), *[h.lstrip("#") for h in (meta.get("hashtags") or [])]]:   # 500 caractères de mots-clés au maximum
            k = (k or "").strip()
            if k and k.lower() not in {x.lower() for x in tags} and total + len(k) + 1 <= 450:
                tags.append(k); total += len(k) + 1
        lang = {"fr": "fr", "en": "en", "es": "es"}.get(meta.get("lang", "fr"), "fr")
        return {"snippet": {"title": title, "description": desc[:4900], "tags": tags, "categoryId": category,
                            "defaultLanguage": lang, "defaultAudioLanguage": lang},
                "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False, "embeddable": True, "publicStatsViewable": True}}

    def publish(self, video, meta, key) -> Result:
        try:
            token = self._token()
        except NotConfigured as e:
            return Result(self.platform, "NOT_CONFIGURED", detail=f"variable manquante: {e}")
        except Exception as e:  # jeton expiré, réseau…
            return Result(self.platform, "FAILED", detail=f"auth: {type(e).__name__} (relancez `./p.sh youtube-login`)")
        try:
            snippet = self.build_snippet(meta, self.privacy, self.category)
            data = open(video, "rb").read()
            h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(len(data))}
            _, hdr, _ = self.http(urllib.request.Request(
                "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                data=json.dumps(snippet).encode(), headers=h, method="POST"))
            loc = {k.lower(): v for k, v in hdr.items()}["location"]
            _, _, out = self.http(urllib.request.Request(loc, data=data, headers={"Content-Type": "video/mp4"}, method="PUT"))
            vid = json.loads(out)["id"]
        except urllib.error.HTTPError as e:
            return Result(self.platform, "FAILED", detail=explain_http_error(e))
        except Exception as e:
            return Result(self.platform, "FAILED", detail=f"{type(e).__name__}: {str(e)[:200]}")
        shorts = meta.get("shorts", True)
        link = f"https://www.youtube.com/shorts/{vid}" if shorts else f"https://www.youtube.com/watch?v={vid}"
        note = ""
        thumb = meta.get("thumbnail")
        if thumb and not shorts:                                      # miniature : vidéos longues seulement
            try:
                img = open(thumb, "rb").read()
                self.http(urllib.request.Request(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}&uploadType=media",
                                                 data=img, headers={"Authorization": f"Bearer {token}", "Content-Type": "image/jpeg"}, method="POST"))
            except Exception as e:
                note = " (miniature non envoyée : la chaîne doit être vérifiée par téléphone sur YouTube)" if "403" in str(e) else " (miniature non envoyée)"
        return Result(self.platform, "PUBLISHED", vid, link + note)
