import json
import urllib.parse
import urllib.request

from .base import NotConfigured, Result, env


def _http(req: urllib.request.Request, timeout=300):
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, dict(r.headers), r.read()


class YouTube:
    platform = "youtube"

    def __init__(self, http=_http): self.http = http

    def _token(self) -> str:
        body = urllib.parse.urlencode({"client_id": env("YOUTUBE_CLIENT_ID"), "client_secret": env("YOUTUBE_CLIENT_SECRET"),
                                       "refresh_token": env("YOUTUBE_REFRESH_TOKEN"), "grant_type": "refresh_token"}).encode()
        _, _, data = self.http(urllib.request.Request("https://oauth2.googleapis.com/token", data=body))
        return json.loads(data)["access_token"]

    def publish(self, video, meta, key) -> Result:
        try:
            token = self._token()
        except NotConfigured as e:
            return Result(self.platform, "NOT_CONFIGURED", detail=f"variable manquante: {e}")
        except Exception as e:  # token expiré, réseau…
            return Result(self.platform, "FAILED", detail=f"auth: {type(e).__name__}")
        try:
            shorts = meta.get("shorts", True)
            title = meta["title"][:100] if (not shorts or "#Shorts" in meta["title"]) else (meta["title"][:90] + " #Shorts")
            snippet = {"snippet": {"title": title, "description": meta["description"] + ("\n#Shorts" if shorts else ""), "categoryId": "10"},
                       "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}
            data = open(video, "rb").read()
            h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8",
                 "X-Upload-Content-Type": "video/mp4", "X-Upload-Content-Length": str(len(data))}
            _, hdr, _ = self.http(urllib.request.Request(
                "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                data=json.dumps(snippet).encode(), headers=h, method="POST"))
            loc = {k.lower(): v for k, v in hdr.items()}["location"]
            _, _, out = self.http(urllib.request.Request(loc, data=data, headers={"Content-Type": "video/mp4"}, method="PUT"))
            return Result(self.platform, "PUBLISHED", json.loads(out)["id"])
        except Exception as e:
            return Result(self.platform, "FAILED", detail=f"{type(e).__name__}: {str(e)[:200]}")
