"""Attente d'un code d'autorisation OAuth sur une adresse locale (127.0.0.1) : commun à YouTube et TikTok."""
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer


def wait_for_code(build_url, port: int = 8085, open_browser: bool = True, say=print, timeout: float = 300.0, state: str = "piano"):
    """Ouvre la page d'autorisation, attend la redirection locale, retourne (code, redirect_uri)."""
    got: dict = {}
    done = threading.Event()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("state", [state])[0] != state:                       # protection : on ignore une redirection qui n'est pas la nôtre
                self.send_response(400); self.end_headers(); return
            got["code"] = (q.get("code") or [""])[0]
            got["error"] = (q.get("error") or [""])[0]
            body = ("<meta charset=utf-8><body style='font-family:sans-serif;padding:40px'><h2>"
                    + ("✅ Connexion réussie" if got["code"] else "❌ Connexion refusée") + "</h2><p>Vous pouvez fermer cet onglet.</p>").encode()
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write(body)
            done.set()

    srv = HTTPServer(("127.0.0.1", port), H)
    redirect = f"http://127.0.0.1:{srv.server_address[1]}/"
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = build_url(redirect)
    say(f"Autorisez l'accès dans la page qui s'ouvre. Sinon ouvrez ce lien :\n{url}")
    if open_browser:
        webbrowser.open(url)
    try:
        if not done.wait(timeout=timeout):
            raise RuntimeError("Délai dépassé : aucune autorisation reçue en 5 minutes.")
    finally:
        srv.shutdown()
    if not got.get("code"):
        raise RuntimeError(f"Autorisation refusée ({got.get('error') or 'inconnue'}).")
    return got["code"], redirect
