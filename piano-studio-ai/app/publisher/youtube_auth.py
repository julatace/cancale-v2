"""Connexion à YouTube une seule fois : ouvre la page d'autorisation Google, récupère le jeton et l'écrit dans .env."""
import json
import os
import threading
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/youtube.upload"


def auth_url(client_id: str, redirect: str, state: str = "piano") -> str:
    q = {"client_id": client_id, "redirect_uri": redirect, "response_type": "code", "scope": SCOPE,
         "access_type": "offline", "prompt": "consent", "state": state}
    return AUTH + "?" + urllib.parse.urlencode(q)


def _post(url: str, data: dict) -> dict:
    req = urllib.request.Request(url, urllib.parse.urlencode(data).encode())
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def exchange_code(code: str, client_id: str, client_secret: str, redirect: str, post=_post) -> str:
    """Échange le code d'autorisation contre un jeton de rafraîchissement (valable durablement)."""
    r = post(TOKEN, {"code": code, "client_id": client_id, "client_secret": client_secret,
                     "redirect_uri": redirect, "grant_type": "authorization_code"})
    if not r.get("refresh_token"):
        raise RuntimeError("Google n'a pas renvoyé de jeton durable. Relancez la connexion et acceptez toutes les autorisations.")
    return r["refresh_token"]


def write_env(path: Path, updates: dict[str, str]) -> None:
    lines = path.read_text().splitlines() if path.exists() else []
    seen = set()
    for i, l in enumerate(lines):
        k = l.split("=", 1)[0].strip()
        if k in updates and "=" in l:
            lines[i] = f"{k}={updates[k]}"; seen.add(k)
    lines += [f"{k}={v}" for k, v in updates.items() if k not in seen]
    path.write_text("\n".join(lines) + "\n")
    try:
        path.chmod(0o600)                                 # le fichier contient des secrets
    except OSError:
        pass


def login(env_path: Path, port: int = 8085, open_browser: bool = True, post=_post, say=print) -> str:
    cid, secret = os.environ.get("YOUTUBE_CLIENT_ID", ""), os.environ.get("YOUTUBE_CLIENT_SECRET", "")
    if not cid or not secret:
        raise RuntimeError("YOUTUBE_CLIENT_ID et YOUTUBE_CLIENT_SECRET manquent dans le fichier .env (voir README, section YouTube).")
    got: dict = {}
    done = threading.Event()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            got["code"] = (q.get("code") or [""])[0]
            got["error"] = (q.get("error") or [""])[0]
            body = ("<meta charset=utf-8><body style='font-family:sans-serif;padding:40px'><h2>"
                    + ("✅ Connexion réussie" if got["code"] else "❌ Connexion refusée") + "</h2><p>Vous pouvez fermer cet onglet.</p>").encode()
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(body)
            done.set()

    srv = HTTPServer(("127.0.0.1", port), H)
    redirect = f"http://127.0.0.1:{srv.server_address[1]}"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = auth_url(cid, redirect)
    say(f"Autorisez l'accès dans la page Google qui s'ouvre. Sinon ouvrez ce lien :\n{url}")
    if open_browser:
        webbrowser.open(url)
    try:
        if not done.wait(timeout=300):
            raise RuntimeError("Délai dépassé : aucune autorisation reçue en 5 minutes.")
    finally:
        srv.shutdown()
    if not got.get("code"):
        raise RuntimeError(f"Autorisation refusée ({got.get('error') or 'inconnue'}).")
    token = exchange_code(got["code"], cid, secret, redirect, post)
    write_env(env_path, {"YOUTUBE_REFRESH_TOKEN": token})
    os.environ["YOUTUBE_REFRESH_TOKEN"] = token
    return token
