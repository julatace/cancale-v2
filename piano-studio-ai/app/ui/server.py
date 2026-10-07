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
from app.director import control, difficulty, pipeline, stock
from app.music_discovery import importer
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

    def start(self, settings, level, formats, publish, count=1, song_id=None) -> bool:
        with self.lock:
            if self.state["status"] == "running":
                return False
            control.CANCEL.clear()
            control.STOP_RECORD.clear()
            self.state = {"status": "running", "params": {"level": level, "formats": formats, "publish": publish, "count": count},
                          "result": None, "error": None, "started": time.time()}
            self.logs.clear()
        threading.Thread(target=self._run, args=(settings, level, formats, publish, count, song_id), daemon=True).start()
        return True

    def _run(self, settings, level, formats, publish, count, song_id=None):
        job = self

        class H(logging.Handler):
            def emit(self, record):
                job._add(record.getMessage())

        h = H(level=logging.INFO)
        lg = logging.getLogger("piano")
        lg.addHandler(h)
        try:
            results = [RUNNER(settings, level=level, formats=formats, publish=publish, song_id=song_id) for _ in range(count)]
            with self.lock:
                self.state.update(status="done", result=results[-1] if count == 1 else results)
        except control.Cancelled:
            self._add("■ Création arrêtée. Synthesia est fermé et l'enregistrement coupé.")
            with self.lock:
                self.state.update(status="cancelled", error=None)
        except Exception as e:  # jamais de plantage silencieux
            self._add(f"✖ ERREUR : {type(e).__name__}: {e}")
            with self.lock:
                self.state.update(status="failed", error=f"{type(e).__name__}: {e}")
        finally:
            lg.removeHandler(h)
            stock.refill_in_background(settings)          # prépare déjà le(s) prochain(s) morceau(x)

    def stop(self) -> bool:
        with self.lock:
            running = self.state["status"] == "running"
        if running:
            control.CANCEL.set()
            self._add("■ Arrêt demandé…")
        return running

    def stop_recording(self) -> bool:
        """Coupe l'enregistrement en cours ; la vidéo est montée avec ce qui est déjà enregistré."""
        with self.lock:
            running = self.state["status"] == "running"
        if running:
            control.STOP_RECORD.set()
            self._add("■ Arrêt de l'enregistrement demandé…")
        return running

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


def _version() -> str:
    try:
        import subprocess
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=Path(__file__).parent, timeout=5).stdout.strip() or "?"
    except Exception:
        return "?"


VERSION = _version()                # version du code réellement chargée par ce serveur
_ENGINE = {"at": 0, "value": None, "busy": False}


def _probe_engine(s):
    """Vérifie en arrière-plan si Synthesia est prêt (peut prendre quelques secondes sur Mac) : la page ne l'attend jamais."""
    try:
        from app.synthesia_controller import mac
        ready = s.get("engine", "auto") != "builtin" and mac.ready(s.get("synthesia", {}))
    except Exception:
        ready = False
    _ENGINE.update(at=time.time(), value="synthesia" if ready else "builtin", busy=False)


def info(s) -> dict:
    """Stock de morceaux d'avance + moteur qui sera utilisé (Synthesia ou rendu intégré)."""
    if time.time() - _ENGINE["at"] > 60 and not _ENGINE["busy"]:
        _ENGINE["busy"] = True
        threading.Thread(target=_probe_engine, args=(s,), daemon=True).start()
    return {"stock": stock.count(s), "stock_target": s.get("stock", {}).get("target", 3), "engine": _ENGINE["value"], "version": VERSION}


def _origin(src: str) -> str:
    src = src or ""
    return "mine" if src.startswith("user_owned: Fourni") else "reserve" if "Mutopia" in src else "auto"


def songs(s) -> list[dict]:
    conn = db.connect(config.resolve(s, "database"))
    rows = conn.execute("SELECT id,title,artist,source,midi_path,created_at FROM songs WHERE license='LEGAL_CONFIRMED' ORDER BY id DESC").fetchall()
    return [{"id": r["id"], "title": r["title"], "artist": r["artist"], "origin": _origin(r["source"]),
             "ready": bool(r["midi_path"] and Path(r["midi_path"]).exists())} for r in rows if r["midi_path"] and Path(r["midi_path"]).exists()]


def import_upload(s, name: str, data: bytes, title: str = "", artist: str = "") -> dict:
    """Import d'un MIDI fourni par l'utilisateur (droits confirmés dans la page). Le fichier est validé avant d'être gardé."""
    stem = Path(name).stem.replace("_", " ").replace("-", " ").strip() or "Mon morceau"
    up = config.resolve(s, "data_dir") / "midi" / "uploads"
    up.mkdir(parents=True, exist_ok=True)
    tmp = up / f"{int(time.time() * 1000)}.mid"
    tmp.write_bytes(data)
    try:
        conn = db.connect(config.resolve(s, "database"))
        r = importer.import_midi(conn, tmp, (title or stem)[:80], (artist or "")[:60], "user_owned",
                                 "Fourni par l'utilisateur (droits confirmés)", dest_dir=config.resolve(s, "data_dir") / "midi")
        if r["status"] == "LEGAL_CONFIRMED":
            conn.execute("UPDATE songs SET source=? WHERE id=?", ("user_owned: Fourni par l'utilisateur (droits confirmés)", r["song_id"]))
            conn.commit()
        return r
    finally:
        tmp.unlink(missing_ok=True)


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

        def _upload(self):
            n = int(self.headers.get("Content-Length", 0) or 0)
            if self.headers.get("X-Rights") != "1":
                return self._json({"error": "Vous devez confirmer que vous avez les droits sur cette musique."}, 400)
            if n <= 0 or n > 8 * 1024 * 1024:
                return self._json({"error": "fichier vide ou trop gros (8 Mo max)"}, 400)
            name = unquote(self.headers.get("X-Filename", "morceau.mid"))
            if not name.lower().endswith((".mid", ".midi")):
                return self._json({"error": "Seuls les fichiers MIDI (.mid) sont acceptés. Un MP3 ne contient pas de notes."}, 400)
            r = import_upload(settings_loader(), name, self.rfile.read(n), unquote(self.headers.get("X-Title", "")), unquote(self.headers.get("X-Artist", "")))
            msg = {"LEGAL_CONFIRMED": "Morceau ajouté.", "DUPLICATE": "Ce morceau est déjà dans votre bibliothèque.",
                   "REJECTED": "Fichier MIDI invalide ou vide."}.get(r["status"], "Morceau non accepté.")
            return self._json({"status": r["status"], "message": msg, "song_id": r.get("song_id")}, 200 if r["status"] in ("LEGAL_CONFIRMED", "DUPLICATE") else 400)

        def _delete_song(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
            s = settings_loader()
            conn = db.connect(config.resolve(s, "database"))
            conn.execute("UPDATE songs SET license='REJECTED' WHERE id=? AND source LIKE 'user_owned: Fourni%'", (int(body.get("id", 0)),))
            conn.commit()
            return self._json({"ok": True})

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
            if u.path == "/api/songs":
                return self._json(songs(s))
            if u.path == "/api/videos":
                return self._json(videos(s))
            if u.path.startswith("/files/"):
                name = Path(unquote(u.path[len("/files/"):])).name          # pas de ../
                f = config.resolve(s, "data_dir") / "rendered" / name
                if f.is_file():
                    return self._send_file(f)
            self._send(404, b'{"error":"not found"}')

        def do_POST(self):
            path = urlparse(self.path).path
            if path not in ("/api/run", "/api/upload", "/api/songs/delete", "/api/stop", "/api/stop-recording"):
                return self._send(404, b'{"error":"not found"}')
            origin = self.headers.get("Origin", "")
            if origin and not (origin.startswith("http://127.0.0.1") or origin.startswith("http://localhost")):
                return self._json({"error": "origine refusée"}, 403)
            if path == "/api/stop-recording":
                return self._json({"ok": True, "was_running": JOB.stop_recording()})
            if path == "/api/stop":
                return self._json({"ok": True, "was_running": JOB.stop()})
            if path == "/api/upload":
                return self._upload()
            if path == "/api/songs/delete":
                return self._delete_song()
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
            if body.get("synthesia", True):
                s = {**s, "engine": "synthesia"}              # Synthesia obligatoire : une erreur s'affiche, pas de repli silencieux
            else:
                s = {**s, "engine": "builtin"}
            if not JOB.start(s, level, formats, bool(body.get("publish", False)), count, int(body["song_id"]) if body.get("song_id") else None):
                return self._json({"error": "une vidéo est déjà en cours de création"}, 409)
            self._json({"ok": True})

    return Handler


def serve(port=8765, open_browser=True, settings_loader=config.load_settings):
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(settings_loader))
    except OSError as e:
        print(f"❌ Le port {port} est déjà utilisé ({e.strerror}) : une ancienne page tourne encore.\n"
              f"   Fermez-la (Ctrl+C dans son Terminal) ou lancez : lsof -ti tcp:{port} | xargs kill")
        raise SystemExit(1)
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
