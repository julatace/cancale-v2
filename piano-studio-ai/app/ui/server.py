"""Interface locale : choisir le niveau (facile / moyen / difficile) et le format (vertical court / horizontal long), puis créer la vidéo."""
import json
import logging
import threading
import time
import webbrowser
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from app import config
from app.database import db
from app.director import difficulty, pipeline
from .page import PAGE

RUNNER = pipeline.run_one          # remplaçable dans les tests
LEVELS_SHOWN = ["facile", "moyen", "difficile"]


class Job:
    """Une seule création à la fois ; les messages du pipeline sont recueillis pour l'affichage en direct."""

    def __init__(self):
        self.lock = threading.Lock()
        self.state = {"status": "idle", "params": None, "result": None, "error": None, "started": None}
        self.logs = deque(maxlen=500)
        self.n = 0

    def _add(self, msg):
        with self.lock:
            self.n += 1
            self.logs.append((self.n, msg))

    def start(self, settings, level, fmt, publish, count=1) -> bool:
        with self.lock:
            if self.state["status"] == "running":
                return False
            self.state = {"status": "running", "params": {"level": level, "format": fmt, "publish": publish, "count": count},
                          "result": None, "error": None, "started": time.time()}
            self.logs.clear()
        threading.Thread(target=self._run, args=(settings, level, fmt, publish, count), daemon=True).start()
        return True

    def _run(self, settings, level, fmt, publish, count):
        job = self

        class H(logging.Handler):
            def emit(self, record):
                job._add(record.getMessage())

        h = H(level=logging.INFO)
        lg = logging.getLogger("piano")
        lg.addHandler(h)
        try:
            results = [RUNNER(settings, level=level, fmt=fmt, publish=publish) for _ in range(count)]
            with self.lock:
                self.state.update(status="done", result=results[-1] if count == 1 else results)
        except Exception as e:  # jamais de plantage silencieux
            self._add(f"✖ ERREUR : {type(e).__name__}: {e}")
            with self.lock:
                self.state.update(status="failed", error=f"{type(e).__name__}: {e}")
        finally:
            lg.removeHandler(h)

    def snapshot(self, since=0):
        with self.lock:
            return {**self.state, "logs": [m for n, m in self.logs if n > since], "last": self.n}


JOB = Job()


def options(s) -> dict:
    d = difficulty.config(s)
    return {
        "levels": [{"key": k, "label": d["levels"][k]["label"], "bpm": d["levels"][k]["bpm"]} for k in LEVELS_SHOWN if k in d["levels"]],
        "formats": [{"key": k, "label": v.get("label", k), "width": v["width"], "height": v["height"],
                     "long": v.get("duration") == "full"} for k, v in s.get("formats", {}).items()],
        "default_format": s.get("default_format", "vertical"),
    }


def videos(s, limit=12) -> list[dict]:
    conn = db.connect(config.resolve(s, "database"))
    rows = conn.execute("SELECT id,title,style,duration,quality_score,status,output_path,created_at FROM videos ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        lvl, _, fmt = (r["style"] or "").partition("|")
        p = Path(r["output_path"] or "")
        out.append({"id": r["id"], "title": r["title"], "level": lvl, "format": fmt, "duration": round(r["duration"] or 0),
                    "quality": r["quality_score"], "status": r["status"], "file": p.name if p.exists() else None, "at": r["created_at"][:16]})
    return out


def make_handler(settings_loader):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body: bytes, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj, ensure_ascii=False, default=str).encode())

        def do_GET(self):
            u = urlparse(self.path)
            s = settings_loader()
            if u.path == "/":
                return self._send(200, PAGE.encode(), "text/html; charset=utf-8")
            if u.path == "/api/options":
                return self._json(options(s))
            if u.path == "/api/status":
                since = int(parse_qs(u.query).get("since", ["0"])[0])
                return self._json(JOB.snapshot(since))
            if u.path == "/api/videos":
                return self._json(videos(s))
            if u.path.startswith("/files/"):
                name = Path(unquote(u.path[len("/files/"):])).name          # pas de ../
                f = config.resolve(s, "data_dir") / "rendered" / name
                if f.is_file():
                    return self._send(200, f.read_bytes(), "video/mp4")
            self._send(404, b'{"error":"not found"}')

        def do_POST(self):
            if urlparse(self.path).path != "/api/run":
                return self._send(404, b'{"error":"not found"}')
            origin = self.headers.get("Origin", "")
            if origin and not (origin.startswith("http://127.0.0.1") or origin.startswith("http://localhost")):
                return self._json({"error": "origine refusée"}, 403)
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
            except json.JSONDecodeError:
                return self._json({"error": "JSON invalide"}, 400)
            s = settings_loader()
            opt = options(s)
            level, fmt = body.get("level") or None, body.get("format") or opt["default_format"]
            if level not in {l["key"] for l in opt["levels"]} | {None}:
                return self._json({"error": "niveau inconnu"}, 400)
            if fmt not in {f["key"] for f in opt["formats"]}:
                return self._json({"error": "format inconnu"}, 400)
            count = max(1, min(int(body.get("count", 1) or 1), 5))
            if not JOB.start(s, level, fmt, bool(body.get("publish", False)), count):
                return self._json({"error": "une vidéo est déjà en cours de création"}, 409)
            self._json({"ok": True})

    return Handler


def serve(port=8765, open_browser=True, settings_loader=config.load_settings):
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(settings_loader))
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    print(f"Interface Piano Studio AI : {url}   (Ctrl+C pour arrêter)")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return srv
