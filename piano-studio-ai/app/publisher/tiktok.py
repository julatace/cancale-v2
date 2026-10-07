"""TikTok (Content Posting API officielle). Deux modes :
 - draft  (défaut) : la vidéo arrive dans la boîte de réception de l'app TikTok ; vous touchez « Publier » (légende à coller).
 - direct : publication immédiate. TikTok impose « privé (vous seul) » tant que l'application n'a pas été approuvée par ses équipes.
NON testé contre le vrai TikTok depuis le conteneur de développement : protocole écrit d'après la documentation officielle."""
import json
import math
import time
import urllib.parse
import urllib.request

from .base import NotConfigured, Result, env

API = "https://open.tiktokapis.com"
AUTH = "https://www.tiktok.com/v2/auth/authorize/"
SCOPES = "user.info.basic,video.upload,video.publish"
MAX_SINGLE = 60 * 1024 * 1024          # au-delà : envoi en morceaux de 30 Mo


def _http(req: urllib.request.Request, timeout=300):
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, dict(r.headers), r.read()


def auth_url(client_key: str, redirect: str, state: str = "piano") -> str:
    return AUTH + "?" + urllib.parse.urlencode({"client_key": client_key, "scope": SCOPES, "response_type": "code",
                                                "redirect_uri": redirect, "state": state})


def exchange_code(code: str, client_key: str, client_secret: str, redirect: str, http=_http) -> dict:
    body = urllib.parse.urlencode({"client_key": client_key, "client_secret": client_secret, "code": code,
                                   "grant_type": "authorization_code", "redirect_uri": redirect}).encode()
    _, _, data = http(urllib.request.Request(API + "/v2/oauth/token/", data=body,
                                             headers={"Content-Type": "application/x-www-form-urlencoded"}))
    r = json.loads(data)
    if not r.get("refresh_token"):
        raise RuntimeError("TikTok n'a pas renvoyé de jeton : " + str(r.get("error_description") or r.get("error") or "réponse inattendue"))
    return r


class TikTok:
    platform = "tiktok"

    def __init__(self, http=_http, mode: str = "draft", sleep=time.sleep):
        self.http, self.mode, self.sleep = http, mode, sleep

    def _json(self, url, payload, token, method="POST"):
        _, _, data = self.http(urllib.request.Request(
            API + url, data=json.dumps(payload).encode(), method=method,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}))
        r = json.loads(data)
        err = r.get("error", {})
        if err and err.get("code") not in (None, "ok"):
            raise RuntimeError(f"{err.get('code')}: {err.get('message', '')}")
        return r.get("data", {})

    def _token(self) -> str:
        body = urllib.parse.urlencode({"client_key": env("TIKTOK_CLIENT_KEY"), "client_secret": env("TIKTOK_CLIENT_SECRET"),
                                       "grant_type": "refresh_token", "refresh_token": env("TIKTOK_REFRESH_TOKEN")}).encode()
        _, _, data = self.http(urllib.request.Request(API + "/v2/oauth/token/", data=body,
                                                      headers={"Content-Type": "application/x-www-form-urlencoded"}))
        r = json.loads(data)
        if not r.get("access_token"):
            raise RuntimeError("jeton TikTok refusé ou expiré : relancez `piano tiktok-login`")
        return r["access_token"]

    def publish(self, video, meta, key) -> Result:
        try:
            token = self._token()
        except NotConfigured as e:
            return Result(self.platform, "NOT_CONFIGURED", detail=f"variable manquante: {e} (voir README, section TikTok)")
        except Exception as e:
            return Result(self.platform, "FAILED", detail=f"auth: {str(e)[:150]}")
        try:
            data = open(video, "rb").read()
            size = len(data)
            chunk = size if size <= MAX_SINGLE else 30 * 1024 * 1024
            total = math.ceil(size / chunk)
            src = {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk, "total_chunk_count": total}
            if self.mode == "direct":
                info = self._json("/v2/post/publish/creator_info/query/", {}, token)
                opts = info.get("privacy_level_options") or ["SELF_ONLY"]
                privacy = "PUBLIC_TO_EVERYONE" if "PUBLIC_TO_EVERYONE" in opts else opts[0]
                caption = (meta.get("tiktok_caption") or meta.get("title") or "")[:2200]
                init = self._json("/v2/post/publish/video/init/", {"post_info": {"title": caption, "privacy_level": privacy,
                                  "disable_duet": False, "disable_comment": False, "disable_stitch": False},
                                  "source_info": src}, token)
            else:
                init = self._json("/v2/post/publish/inbox/video/init/", {"source_info": src}, token)
            for i in range(total):
                part = data[i * chunk:(i + 1) * chunk]
                self.http(urllib.request.Request(init["upload_url"], data=part, method="PUT", headers={
                    "Content-Type": "video/mp4", "Content-Length": str(len(part)),
                    "Content-Range": f"bytes {i * chunk}-{i * chunk + len(part) - 1}/{size}"}))
            pid = init.get("publish_id", "")
            if self.mode == "direct":
                for _ in range(12):                              # suivi du traitement par TikTok (jusqu'à ~1 min)
                    st = self._json("/v2/post/publish/status/fetch/", {"publish_id": pid}, token).get("status", "")
                    if st == "PUBLISH_COMPLETE":
                        return Result(self.platform, "PUBLISHED", pid, f"privacy={privacy}")
                    if st == "FAILED":
                        raise RuntimeError("TikTok a refusé la vidéo")
                    self.sleep(5)
                return Result(self.platform, "PUBLISHED", pid, f"envoyée, traitement en cours (privacy={privacy})")
            return Result(self.platform, "DRAFT", pid, "dans la boîte de réception de l'app TikTok : ouvrez-la et touchez « Publier »")
        except Exception as e:
            return Result(self.platform, "FAILED", detail=f"{type(e).__name__}: {str(e)[:200]}")


def login(env_path, port: int = 8085, open_browser: bool = True, http=_http, say=print) -> str:
    import os
    from .oauth_loopback import wait_for_code
    from .youtube_auth import write_env
    key, secret = os.environ.get("TIKTOK_CLIENT_KEY", ""), os.environ.get("TIKTOK_CLIENT_SECRET", "")
    if not key or not secret:
        raise RuntimeError("TIKTOK_CLIENT_KEY et TIKTOK_CLIENT_SECRET manquent dans le fichier .env (voir README, section TikTok).")
    code, redirect = wait_for_code(lambda r: auth_url(key, r), port, open_browser, say)
    tok = exchange_code(code, key, secret, redirect, http)
    write_env(env_path, {"TIKTOK_REFRESH_TOKEN": tok["refresh_token"]})
    os.environ["TIKTOK_REFRESH_TOKEN"] = tok["refresh_token"]
    return tok["refresh_token"]
