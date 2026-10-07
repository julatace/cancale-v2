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
from app.director import difficulty, pipeline, stock
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

    def start(self, settings, level, formats, publish, count=1) -> bool:
        with self.lock:
            if self.state["status"] == "running":
                return False
            self.state = {"status": "running", "params": {"level": level, "formats": formats, "publish": publish, "count": count},
                          "result": None, "error": None, "started": time.time()}
            self.logs.clear()
        threading.Thread(target=self._run, args=(settings, level, formats, publish, count), daemon=True).start()
        return True

    def _run(self, settings, level, formats, publish, count):
        job = self

        class H(logging.Handler):
            def emit(self, record):
                job._add(record.getMessage())

        h = H(level=logging.INFO)
        lg = logging.getLogger("piano")
        lg.addHandler(h)
        try:
            results = [RUNNER(settings, level=level, formats=formats, publish=publish) for _ in range(count)]
            with self.lock:
                self.state.update(status="done", result=results[-1] if count == 1 else results)
        except Exception as e:  # jamais de plantage silencieux
            self._add(f"✖ ERREUR : {type(e).__name__}: {e}")
            with self.lock:
                self.state.update(status="failed", error=f"{type(e).__name__}: {e}")
        finally:
            lg.removeHandler(h)
            stock.refill_in_background(settings)          # prépare déjà le(s) prochain(s) morceau(x)

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
        "default_formats": s.get("ui_default_formats", [s.get("default_format", "vertical")]),
    }


_ENGINE = {"at": 0, "value": None}


def info(s) -> dict:
    """Stock de morceaux d'avance + moteur qui sera utilisé (Synthesia ou rendu intégré)."""
    if time.time() - _ENGINE["at"] > 60:
        try:
            from app.synthesia_controller import mac
            ready = s.get("engine", "auto") != "builtin" and mac.ready(s.get("synthesia", {}))
        except Exception:
            ready = False
        _ENGINE.update(at=time.time(), value="synthesia" if ready else "builtin")
    return {"stock": stock.count(s), "stock_target": s.get("stock", {}).get("target", 3), "engine": _ENGINE["value"]}


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

        def _send_file(self, f: Path):
            """Vidéo avec prise en charge des « Range » (indispensable pour lire dans Safari)."""
            size = f.stat().st_size
            start, end, code = 0, size - 1, 200
            rng = self.headers.get("Range", "")
            if rng.startswith("bytes="):
                a, _, b = rng[6:].partition("-")
                start = int(a) if a else max(size - int(b or 0), 0)
                end = min(int(b), size - 1) if (b and a) else size - 1
                code = 206
            self.send_response(code)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            if code == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            with open(f, "rb") as fh:
                fh.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = fh.read(min(1 << 20, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)

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
            if u.path == "/api/info":
                return self._json(info(s))
            if u.path == "/api/videos":
                return self._json(videos(s))
            if u.path.startswith("/files/"):
                name = Path(unquote(u.path[len("/files/"):])).name          # pas de ../
                f = config.resolve(s, "data_dir") / "rendered" / name
                if f.is_file():
                    return self._send_file(f)
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
            level = body.get("level") or None
            formats = body.get("formats") or ([body["format"]] if body.get("format") else opt["default_formats"])
            if level not in {l["key"] for l in opt["levels"]} | {None}:
                return self._json({"error": "niveau inconnu"}, 400)
            if not formats or not all(f in {x["key"] for x in opt["formats"]} for f in formats):
                return self._json({"error": "format inconnu"}, 400)
            count = max(1, min(int(body.get("count", 1) or 1), 5))
            if not JOB.start(s, level, formats, bool(body.get("publish", False)), count):
                return self._json({"error": "une vidéo est déjà en cours de création"}, 409)
            self._json({"ok": True})

    return Handler


def serve(port=8765, open_browser=True, settings_loader=config.load_settings):
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(settings_loader))
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    print(f"Interface Piano Studio AI : {url}   (Ctrl+C pour arrêter)")
    stock.refill_in_background(settings_loader())         # réserve de morceaux prête avant même le premier clic
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return srv
