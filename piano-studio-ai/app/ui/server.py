"""Interface locale : choisir le niveau (facile / moyen / difficile) et le format (vertical court / horizontal long), puis créer la vidéo."""
import json
import os
import logging
import threading
import time
import webbrowser
from datetime import date, datetime, timedelta, timezone
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from app import config, notify
from app.director import progress
from app.scheduler import autopilot
from app.database import db
from app.director import control, difficulty, pipeline, stock
from app.music_discovery import importer, inbox, search as msearch, trends as mtrends
from app.scheduler import queue as squeue
from .page import PAGE

RUNNER = pipeline.run_one          # remplaçable dans les tests
LEVELS_SHOWN = ["facile", "moyen", "difficile"]


class QuietServer(ThreadingHTTPServer):
    """Le navigateur coupe souvent une lecture vidéo en cours : ces « connexion réinitialisée » sont normales, on ne les affiche pas."""
    daemon_threads = True

    def handle_error(self, request, client_address):
        import sys
        if isinstance(sys.exc_info()[1], (ConnectionResetError, BrokenPipeError, ConnectionAbortedError)):
            return
        super().handle_error(request, client_address)


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

    def start(self, settings, level, formats, publish, count=1, song_id=None, lang=None, plan=None) -> bool:
        with self.lock:
            if self.state["status"] == "running":
                return False
            control.CANCEL.clear()
            control.STOP_RECORD.clear()
            self._planned = []
            self.state = {"status": "running", "params": {"level": level, "formats": formats, "publish": publish, "count": count, "plan": bool(plan)},
                          "result": None, "error": None, "started": time.time()}
            self.logs.clear()
        threading.Thread(target=self._run, args=(settings, level, formats, publish, count, song_id, lang, plan), daemon=True).start()
        return True

    def start_task(self, name, fn) -> bool:
        """Tâche courte (publier maintenant, publications programmées…) avec le même journal en direct que la création."""
        with self.lock:
            if self.state["status"] == "running":
                return False
            control.CANCEL.clear()
            self.state = {"status": "running", "params": {"task": name}, "result": None, "error": None, "started": time.time()}
            self.logs.clear()

        def work():
            job = self

            class H(logging.Handler):
                def emit(self, record):
                    job._add(record.getMessage())

            h = H(level=logging.INFO)
            lg = logging.getLogger("piano")
            lg.addHandler(h)
            try:
                res = fn()
                with self.lock:
                    self.state.update(status="done", result={"task": name, "summary": res})
            except control.Cancelled:
                self._add("■ Envoi arrêté. Les vidéos déjà envoyées le restent, les autres n'ont pas été touchées.")
                with self.lock:
                    self.state.update(status="cancelled", error=None)
            except Exception as e:
                self._add(f"✖ ERREUR : {type(e).__name__}: {e}")
                with self.lock:
                    self.state.update(status="failed", error=f"{type(e).__name__}: {e}")
            finally:
                lg.removeHandler(h)

        threading.Thread(target=work, daemon=True).start()
        return True

    def _run(self, settings, level, formats, publish, count, song_id=None, lang=None, plan=None):
        job = self

        class H(logging.Handler):
            def emit(self, record):
                job._add(record.getMessage())

        h = H(level=logging.INFO)
        lg = logging.getLogger("piano")
        lg.addHandler(h)
        try:
            results = self._produce(settings, level, formats, publish, count, song_id, lang, plan)
            if not plan:                                                  # création simple : ce sont ces vidéos-là, et elles seules, qui sont « les dernières »
                squeue.set_last_batch([v["video_id"] for r in results for v in (r.get("videos") or [r]) if v.get("video_id")])
            with self.lock:
                self.state.update(status="done", result=results[-1] if count == 1 else results,
                                  planned=[{"title": p["title"], "run_at": p["run_at"], "format": p["format"]} for p in getattr(self, "_planned", [])],
                                  failures=list(getattr(self, "_fails", [])), waiting=list(getattr(self, "_waiting", [])))
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

    def _preflight(self):
        """Contrôle avant départ : mieux vaut refuser tout de suite que d'échouer à la fin d'un long lot."""
        import shutil
        if not shutil.which("ffmpeg"):
            raise RuntimeError("FFmpeg est introuvable (brew install ffmpeg)")
        free = shutil.disk_usage(Path(__file__).resolve().parents[2]).free / 1e9
        if free < 2:
            raise RuntimeError(f"Disque presque plein ({free:.1f} Go libres) : libérez de la place avant de créer des vidéos")
        if free < 5:
            self._add(f"⚠ Seulement {free:.1f} Go libres : les vidéos publiées seront supprimées au fur et à mesure.")

    def _produce(self, settings, level, formats, publish, count, song_id, lang, plan):
        """Crée `count` vidéos ; en mode « semaine » : s'arrête quand le temps alloué est écoulé, puis programme les publications."""
        self._preflight()
        self._count, self._done = count, 0
        progress.reset()
        if not plan:
            return [RUNNER(settings, level=level, formats=formats, publish=publish, song_id=song_id, lang=lang) for _ in range(count)]
        budget = float(plan.get("minutes") or 0) * 60                  # 0 = pas de limite (mode agenda)
        t0, results, good_ids, attempts, done_groups = time.time(), [], [], 0, []
        max_attempts = count + min(count, 4)                            # une création ratée est refaite (avec un autre morceau), dans la limite de 4 reprises
        self._planned = []
        self._fails = []
        self._waiting = []
        squeue.set_last_batch([])                                        # nouvelle fabrication : on repart d'une liste vide
        while len(good_ids) < count and attempts < max_attempts:
            spent = time.time() - t0
            done = len(good_ids)
            if budget and done and spent + (spent / done) * 0.8 > budget:
                self._add(f"⏱ Temps alloué ({plan['minutes']:g} min) bientôt écoulé : {done} création(s) faite(s).")
                break
            attempts += 1
            self._done = done
            progress.reset()
            self._add(f"━━ Vidéo {done + 1}/{count} ━━" + (f" (reprise {attempts - done - 1})" if attempts - done - 1 > 0 else ""))
            try:
                res = RUNNER(settings, level=level, formats=formats, publish=False, song_id=song_id, lang=lang)
            except control.Cancelled:
                raise
            except Exception as e:
                self._add(f"✖ Cette création a échoué : {type(e).__name__}: {e}")
                if "Plus aucun morceau" in str(e):                      # plus rien à fabriquer : inutile d'insister
                    break
                continue
            results.append(res)
            ok_videos = [v for v in (res.get("videos") or [res]) if v.get("video_id") and v.get("status") != "FAILED"]
            if not ok_videos:
                bad = next((v.get("error") for v in (res.get("videos") or [res]) if v.get("error")), "contrôle qualité refusé")
                self._add(f"↻ Cette vidéo a échoué ({str(bad)[:120]}) : j'en refais une autre avec un autre morceau.")
                continue
            good_ids += [v["video_id"] for v in ok_videos]
            squeue.set_last_batch(good_ids)
            k = len(done_groups); done_groups.append([v["video_id"] for v in ok_videos])
            conn0 = db.connect(config.resolve(settings, "database"))
            slots = plan.get("slots") or []
            slot = None if plan.get("immediate") or k >= len(slots) else slots[k]
            for v in ok_videos:                               # dès le montage : envoi aux réseaux, programmé DANS chaque réseau à la date prévue
                nice = f"{slot:%d/%m %H:%M}" if slot else "tout de suite"
                self._add(f"🚀 « {v.get('title', '')[:50]} » : envoi aux réseaux ({nice})…")
                try:
                    res = squeue.publish_video(settings, conn0, v["video_id"], publish_at=slot)
                except Exception as e:
                    self._add(f"✖ Envoi impossible : {e}")
                    continue
                for x in res:
                    if x["status"] == "WAITING":
                        self._add(f"   ⏳ {x['platform']} : {x['detail']}")
                        self._waiting.append(f"« {v.get('title', '')[:45]} » → YouTube : {x['detail']}")
                        continue
                    self._add(f"   {'✓' if x['status'] in squeue.GOOD else '✖'} {x['platform']} : {x['status']}" + (f" — {x['detail'][:100]}" if x["status"] in ("FAILED", "UNCERTAIN") else ""))
                    if x["status"] in ("FAILED", "UNCERTAIN"):
                        self._fails.append(f"{x['platform']} — « {v.get('title', '')[:45]} » : {x['detail'][:260]}")
                if slot and squeue.native_time(slot):
                    self._planned.append({"title": v.get("title", ""), "run_at": squeue.native_time(slot).isoformat(timespec="minutes"), "format": v.get("format", "")})
        planned = self._planned
        n_slots = len({p["run_at"] for p in planned})
        if planned:
            self._add(f"🗓 {n_slots} vidéo(s) programmée(s) DANS TikTok et YouTube : du {planned[0]['run_at'].replace('T', ' ')} au {planned[-1]['run_at'].replace('T', ' ')}.")
            notify.send("Piano Studio", f"{n_slots} vidéo(s) programmée(s) dans TikTok et YouTube.", key=f"planned-{planned[-1]['run_at']}")
        elif done_groups:
            self._add(f"🚀 {len(done_groups)} vidéo(s) envoyée(s) aux réseaux.")
        else:
            self._add("Aucune vidéo réussie.")
        if self._fails:
            notify.send("Piano Studio", f"{len(self._fails)} envoi(s) à vérifier : ouvre la page de l'agent.", key=f"fails-{len(self._fails)}-{len(good_ids)}")
        if len(good_ids) < count:
            self._add(f"⚠ {len(good_ids)} vidéo(s) réussie(s) sur {count} demandée(s) : relance « Fabriquer et programmer l'agenda » pour compléter.")
        return results

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
            return {**self.state, "logs": [m for n, m in self.logs if n > since], "last": self.n,
                    "progress": {**progress.get(), "done": getattr(self, "_done", 0), "count": getattr(self, "_count", 0)}}


JOB = Job()


def options(s) -> dict:
    d = difficulty.config(s)
    return {
        "levels": [{"key": k, "label": d["levels"][k]["label"], "bpm": d["levels"][k]["bpm"]} for k in LEVELS_SHOWN if k in d["levels"]],
        "formats": [{"key": k, "label": v.get("label", k), "width": v["width"], "height": v["height"],
                     "long": v.get("duration") == "full"} for k, v in s.get("formats", {}).items()],
        "default_format": s.get("default_format", "vertical"),
        "default_formats": s.get("ui_default_formats", [s.get("default_format", "vertical")]),
        "languages": [{"key": "fr", "label": "Français"}, {"key": "en", "label": "English"}, {"key": "es", "label": "Español"}],
        "default_language": s.get("language", "fr"),
        "max_record_seconds": int(s.get("synthesia", {}).get("max_record_seconds", 90)),
        "youtube_daily": int(s.get("youtube", {}).get("max_uploads_per_day", 4)),
        "countries": [{"key": k, "label": v} for k, v in mtrends.COUNTRIES.items()],
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
        ready = s.get("style", "sketch") == "synthesia" and s.get("engine", "auto") != "builtin" and mac.ready(s.get("synthesia", {}))
    except Exception:
        ready = False
    _ENGINE.update(at=time.time(), value="synthesia" if ready else "builtin", busy=False)


def info(s) -> dict:
    """Stock de morceaux d'avance + moteur qui sera utilisé (Synthesia ou rendu intégré)."""
    if time.time() - _ENGINE["at"] > 60 and not _ENGINE["busy"]:
        _ENGINE["busy"] = True
        threading.Thread(target=_probe_engine, args=(s,), daemon=True).start()
    return {"stock": stock.count(s), "stock_target": s.get("stock", {}).get("target", 3), "engine": _ENGINE["value"], "version": VERSION, "only_mine": bool(s.get("songs", {}).get("only_mine", False)), "to_make": my_songs_waiting(s),
            "youtube": s.get("youtube", {}).get("mode") == "web" or all(os.environ.get(k) for k in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")),
            "tiktok": s.get("tiktok", {}).get("mode") == "web" or all(os.environ.get(k) for k in ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REFRESH_TOKEN"))}


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
    raw = Path(name).stem.replace("_", " ").strip()
    for bad, good in (("Mai tre", "Maître"), ("Ã©", "é"), ("Ã¨", "è"), ("Ãª", "ê")):       # accents abîmés dans les noms de fichiers
        raw = raw.replace(bad, good)
    if " - " in raw and not (title or artist):             # « Artiste - Titre.mid » : l'artiste et le titre sont lus dans le nom du fichier
        artist, title = (x.strip() for x in raw.split(" - ", 1))
    stem = raw.replace("-", " ").strip() or "Mon morceau"
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
    rows = conn.execute("SELECT id,title,style,duration,quality_score,status,output_path,meta,created_at FROM videos ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        lvl, _, fmt = (r["style"] or "").partition("|")
        p = Path(r["output_path"] or "")
        out.append({"id": r["id"], "title": r["title"], "level": lvl, "format": fmt, "duration": round(r["duration"] or 0),
                    "quality": r["quality_score"], "status": r["status"], "file": p.name if p.exists() else None, "at": r["created_at"][:16],
                    "post": json.loads(r["meta"]) if r["meta"] else None})
    return out


def my_songs_waiting(s) -> int:
    """Morceaux fournis par l'utilisateur qui n'ont pas encore eu leur vidéo (hors délai de réutilisation)."""
    conn = db.connect(config.resolve(s, "database"))
    rows = conn.execute("SELECT id, midi_path FROM songs WHERE license='LEGAL_CONFIRMED' AND source LIKE 'user_owned: Fourni%'").fetchall()
    return sum(1 for r in rows if r["midi_path"] and Path(r["midi_path"]).exists() and db.song_usable(conn, r["id"], s["same_song_cooldown_days"])[0])


def schedule_view(s) -> dict:
    conn = db.connect(config.resolve(s, "database"))
    squeue.drop_orphans(conn)                                        # anciennes lignes sans objet (vidéo publiée ou supprimée)
    rv = squeue.ready_videos(conn)
    return {"items": squeue.listing(conn), "unscheduled": squeue.unscheduled(conn), "ready": len(rv), "ready_titles": [f"{v['title']} ({v['format'] or '?'})" for v in rv[:8]]}


def health(s) -> dict:
    """Bilan des dernières 24 h : ce qui est parti, ce qui a échoué, état du disque. Pour voir d'un coup d'œil que tout tourne."""
    import shutil
    cn = db.connect(config.resolve(s, "database"))
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    pubs = {}
    for r in cn.execute("SELECT platform, status, COUNT(*) n FROM publications WHERE published_at>=? GROUP BY platform, status", (since,)):
        pubs.setdefault(r["platform"], {})[r["status"]] = r["n"]
    errs = [{"stage": r["stage"], "message": (r["message"] or "")[:160], "at": r["timestamp"]}
            for r in cn.execute("SELECT stage, message, timestamp FROM errors WHERE timestamp>=? ORDER BY id DESC LIMIT 5", (since,))]
    nxt = cn.execute("SELECT MIN(run_at) m FROM schedule WHERE status='DONE' AND run_at>?", (squeue._utc(datetime.now(timezone.utc)),)).fetchone()["m"]
    free = shutil.disk_usage(config.ROOT).free / 1e9
    ok = sum(n for d in pubs.values() for st, n in d.items() if st in squeue.GOOD)
    bad = sum(n for d in pubs.values() for st, n in d.items() if st not in squeue.GOOD)
    return {"published": ok, "failed": bad, "platforms": pubs, "errors": errs, "next": nxt, "disk_gb": round(free, 1),
            "level": "bad" if bad or free < 3 else "ok"}


PILOT = autopilot.AutoPilot()


def autopilot_tick(s, start=None):
    """Un tour du pilote : fabrique ce qui manque dans l'agenda (jamais deux fabrications en même temps)."""
    cn = db.connect(config.resolve(s, "database"))
    idle = JOB.state["status"] != "running"
    if PILOT.running and idle:                                   # la fabrication lancée par le pilote est terminée : on en tire les conséquences
        planned = len(getattr(JOB, "_planned", []) or [])
        PILOT.finished(planned, JOB.state["status"] == "failed")
    files = inbox.waiting(s)
    rights = inbox.rights_confirmed(s)
    PILOT.blocked_files = 0 if rights else files
    miss = PILOT.decide(s, cn, idle and not PILOT.running, my_songs_waiting(s) + (files if rights else 0))
    if not miss:
        return False
    try:
        slots = squeue.slots_for_days(miss, autopilot.conf(s)["times"])[:30]
    except Exception:
        return False
    if not slots:
        return False
    opt = options(s)
    plan = {"slots": slots, "immediate": False, "times": squeue.parse_times(autopilot.conf(s)["times"]) or ["12:30", "19:00"]}
    s2 = {**s, "style": s.get("style", "sketch") if s.get("style") == "synthesia" else "sketch"}
    ok = (start or JOB.start)(s2, None, opt["default_formats"], False, len(slots), None, None, plan)
    if ok:
        PILOT.started()
    return ok


def due_runner(settings_loader, every=30, stop=None):
    """Tant que l'interface est ouverte : surveille ton dossier MIDI. L'app ne publie JAMAIS elle-même : c'est TikTok / YouTube qui publient à l'heure."""
    def loop():
        while not (stop and stop.is_set()):
            try:
                s = settings_loader()
                inbox.LAST_CHECK["at"] = time.time()
                if inbox.waiting(s) and inbox.rights_confirmed(s):          # nouveaux sons dans ton dossier : importés tout seuls
                    inbox.scan(s, import_upload)
                autopilot_tick(s)
                cn = db.connect(config.resolve(s, "database"))
                if squeue.waiting_youtube(cn) and squeue.youtube_capacity(s, cn) > 0:       # la limite quotidienne de YouTube s'est libérée : on reprend
                    JOB.start_task("youtube-reprise", lambda: f"{squeue.resume_waiting(s, db.connect(config.resolve(s, 'database')), say=logging.getLogger('piano').info)} vidéo(s) envoyée(s) à YouTube")
            except Exception as e:
                logging.getLogger("piano").warning("programmation : %s", e)
            time.sleep(every)
    threading.Thread(target=loop, daemon=True).start()


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
            self.send_header("Content-Type", "image/jpeg" if f.suffix.lower() == ".jpg" else "video/mp4")
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
            if not name.lower().endswith((".mid", ".midi", ".kar")):
                return self._json({"error": "Seuls les fichiers MIDI (.mid, .midi, .kar) sont acceptés. Un MP3 ne contient pas de notes."}, 400)
            r = import_upload(settings_loader(), name, self.rfile.read(n), unquote(self.headers.get("X-Title", "")), unquote(self.headers.get("X-Artist", "")))
            msg = {"LEGAL_CONFIRMED": "Morceau ajouté.", "DUPLICATE": "Ce morceau est déjà dans votre bibliothèque.",
                   "REJECTED": "Fichier MIDI invalide ou vide."}.get(r["status"], "Morceau non accepté.")
            return self._json({"status": r["status"], "message": msg, "song_id": r.get("song_id")}, 200 if r["status"] in ("LEGAL_CONFIRMED", "DUPLICATE") else 400)

        def _inbox_post(self):
            """Réception d'un MIDI envoyé par un autre programme : le corps est le fichier, X-Filename son nom. Droits : voir inbox.py."""
            s = settings_loader()
            tok = os.environ.get("INBOX_TOKEN", "")
            if tok and self.headers.get("X-Token", "") != tok:
                return self._json({"error": "jeton refusé"}, 403)
            if not inbox.rights_confirmed(s):
                return self._json({"error": "droits non confirmés : coche la case dans la page (Boîte de réception) avant d'envoyer"}, 403)
            n = int(self.headers.get("Content-Length", 0) or 0)
            name = Path(unquote(self.headers.get("X-Filename", "morceau.mid"))).name
            if n <= 0 or n > inbox.MAX_BYTES or not name.lower().endswith(inbox.EXT):
                return self._json({"error": "fichier .mid/.midi/.kar de 8 Mo maximum attendu (en-tête X-Filename)"}, 400)
            (inbox.folder(s) / name).write_bytes(self.rfile.read(n))
            meta = {k: unquote(self.headers.get(h, "")) for k, h in (("title", "X-Title"), ("artist", "X-Artist")) if self.headers.get(h)}
            if meta:
                (inbox.folder(s) / name).with_suffix(".json").write_text(json.dumps(meta, ensure_ascii=False))
            res = inbox.scan(s, import_upload)
            return self._json({"results": res})

        def _plan(self, s, body):
            """Programme les vidéos prêtes (toutes, ou celles demandées) sur les créneaux choisis."""
            try:
                first = date.fromisoformat(body.get("first_day") or (date.today() + timedelta(days=1)).isoformat())
                per_day = min(max(int(body.get("per_day", 2) or 2), 1), 6)
            except ValueError:
                return self._json({"error": "date invalide"}, 400)
            conn = db.connect(config.resolve(s, "database"))
            last = {v["id"] for v in squeue.ready_videos(conn)}                     # seulement la dernière fabrication, jamais d'anciennes vidéos
            ids = [int(i) for i in body.get("video_ids") or []] or [v["id"] for v in squeue.unscheduled(conn) if v["id"] in last]
            if not ids:
                return self._json({"error": "Aucune vidéo prête à programmer. Créez-en d'abord."}, 400)
            at = body.get("at")                              # une seule vidéo à une date/heure précise (« mardi 19 h »)
            if at:
                try:
                    when = [datetime.fromisoformat(at).astimezone()]
                except ValueError:
                    return self._json({"error": "date/heure invalide"}, 400)
            elif body.get("days") is not None:
                try:
                    when = squeue.slots_for_days(body["days"], body.get("times"))
                except (ValueError, KeyError, TypeError):
                    return self._json({"error": "agenda invalide"}, 400)
                if not when:
                    return self._json({"error": "Choisis au moins une vidéo sur un jour à venir dans l'agenda."}, 400)
                ids = ids[:len(when)]
            else:
                when = squeue.slots(first, len(ids), per_day, squeue.parse_times(body.get("times") or ["12:30", "19:00"]))
            pairs = squeue.assign(conn, ids, when)                    # chaque vidéo est envoyée aux réseaux, qui la programment eux-mêmes à cette date
            if not pairs:
                return self._json({"error": "Aucune vidéo prête à programmer."}, 400)

            def work_pairs():
                c2 = db.connect(config.resolve(s, "database"))
                ok = 0
                for vid, dt in pairs:
                    logging.getLogger("piano").info("🚀 Vidéo %s : envoi aux réseaux (%s)…", vid, f"{dt:%d/%m %H:%M}" if squeue.native_time(dt) else "tout de suite")
                    try:
                        res = squeue.publish_video(s, c2, vid, publish_at=dt)
                        ok += any(x["status"] in squeue.GOOD for x in res)
                    except Exception as e:
                        logging.getLogger("piano").info("✖ Envoi impossible : %s", e)
                return f"{ok} vidéo(s) envoyée(s) sur {len(pairs)}"
            if not JOB.start_task("schedule-ready", work_pairs):
                return self._json({"error": "une opération est déjà en cours"}, 409)
            return self._json({"ok": True, "message": f"Envoi de {len(pairs)} vidéo(s) aux réseaux…"})

        def _publish_now(self, s, body):
            vid = int(body.get("video_id", 0))

            def work():
                conn = db.connect(config.resolve(s, "database"))
                res = squeue.publish_video(s, conn, vid)
                return "; ".join(f"{r['platform']}: {r['status']}" for r in res) or "aucune plateforme configurée"

            if not JOB.start_task("publish", work):
                return self._json({"error": "une opération est déjà en cours"}, 409)
            return self._json({"ok": True})

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
            if u.path == "/api/search":
                q = parse_qs(u.query).get("q", [""])[0]
                return self._json(msearch.search(s, q))
            if u.path == "/api/check-platforms":
                from app.publisher import adapters as _ads
                out = []
                for ad in _ads(s):
                    if hasattr(ad, "check"):
                        ok, msg = ad.check()
                        out.append({"platform": ad.platform, "ok": ok, "message": msg})
                return self._json(out)
            if u.path == "/api/latest":
                return self._json(msearch.latest())
            if u.path == "/api/popular":
                return self._json(msearch.popular())
            if u.path == "/api/trends":
                qs = parse_qs(u.query)
                try:
                    items = mtrends.fetch_trends(qs.get("country", ["fr"])[0], qs.get("genre", ["all"])[0])
                    return self._json({"items": items, "message": ""})
                except mtrends.TrendsUnavailable as e:
                    return self._json({"items": [], "message": str(e)})
            if u.path == "/api/inbox":
                return self._json({**inbox.status(s), "to_make": my_songs_waiting(s)})
            if u.path == "/api/schedule":
                return self._json(schedule_view(s))
            if u.path == "/api/health":
                return self._json(health(s))
            if u.path == "/api/autopilot":
                return self._json(PILOT.status(s, db.connect(config.resolve(s, "database")), my_songs_waiting(s)))
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
            if path not in ("/api/run", "/api/upload", "/api/songs/delete", "/api/stop", "/api/stop-recording", "/api/import-found",
                        "/api/schedule/plan", "/api/schedule/cancel", "/api/publish-now", "/api/week", "/api/inbox", "/api/inbox/rights", "/api/inbox/scan", "/api/folder", "/api/setting", "/api/publish-ready", "/api/autopilot"):
                return self._send(404, b'{"error":"not found"}')
            origin = self.headers.get("Origin", "")
            if origin and not (origin.startswith("http://127.0.0.1") or origin.startswith("http://localhost")):
                return self._json({"error": "origine refusée"}, 403)
            if path == "/api/import-found":
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
                try:
                    r = msearch.import_found(settings_loader(), str(body.get("page", "")))
                except Exception as e:
                    return self._json({"error": f"Import impossible : {e}"}, 400)
                msg = {"LEGAL_CONFIRMED": "MIDI ajouté à votre bibliothèque.", "DUPLICATE": "Déjà dans votre bibliothèque."}.get(r["status"], "Non accepté.")
                return self._json({**r, "message": msg}, 200 if r["status"] in ("LEGAL_CONFIRMED", "DUPLICATE") else 400)
            if path == "/api/stop-recording":
                return self._json({"ok": True, "was_running": JOB.stop_recording()})
            if path == "/api/stop":
                return self._json({"ok": True, "was_running": JOB.stop()})
            if path == "/api/upload":
                return self._upload()
            if path == "/api/inbox":
                return self._inbox_post()
            if path == "/api/songs/delete":
                return self._delete_song()
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
            except json.JSONDecodeError:
                return self._json({"error": "JSON invalide"}, 400)
            s = settings_loader()
            if path == "/api/setting":                         # réglages modifiables depuis la page (liste blanche)
                if body.get("key") == "max_record_seconds":
                    try:
                        n = int(float(body.get("value")))
                    except (TypeError, ValueError):
                        return self._json({"error": "valeur invalide"}, 400)
                    if not 30 <= n <= 300:
                        return self._json({"error": "choisis entre 30 secondes et 5 minutes"}, 400)
                    config.save_local("synthesia", {"max_record_seconds": n})
                    return self._json({"max_record_seconds": n})
                return self._json({"error": "réglage inconnu"}, 400)
            if path == "/api/autopilot":
                cur = autopilot.conf(settings_loader())
                try:
                    new = {"enabled": bool(body.get("enabled", cur["enabled"])), "per_day": int(body.get("per_day", cur["per_day"])), "days": int(body.get("days", cur["days"]))}
                    if body.get("times"):
                        if not squeue.parse_times(body["times"]):
                            return self._json({"error": "heures invalides (ex. 12:30, 19:00)"}, 400)
                        new["times"] = body["times"]
                except (TypeError, ValueError):
                    return self._json({"error": "réglage invalide"}, 400)
                config.save_local("autopilot", new)
                if new["enabled"]:
                    PILOT.next_try, PILOT.fails = 0.0, 0
                s2 = settings_loader()
                return self._json(PILOT.status(s2, db.connect(config.resolve(s2, "database")), my_songs_waiting(s2)))
            if path == "/api/folder":
                d = Path(str(body.get("path", "")).strip()).expanduser()
                if not str(body.get("path", "")).strip() or not d.is_dir():
                    return self._json({"error": f"Dossier introuvable : {d}. Vérifie le chemin (ex. ~/Desktop/MIDI)."}, 400)
                config.save_local("inbox", {"watch": [str(d)]})
                return self._json({**inbox.status(settings_loader()), "to_make": my_songs_waiting(settings_loader())})
            if path == "/api/inbox/scan":
                s = settings_loader()
                if not inbox.rights_confirmed(s):
                    return self._json({"error": "Coche d'abord la case de confirmation des droits."}, 403)
                res = inbox.scan(s, import_upload)
                ok = sum(1 for r in res if r["status"] == "LEGAL_CONFIRMED")
                return self._json({"imported": ok, "duplicates": sum(1 for r in res if r["status"] == "DUPLICATE"),
                                   "errors": [f"{r['file']}: {r.get('detail') or r['status']}" for r in res if r["status"] not in ("LEGAL_CONFIRMED", "DUPLICATE")],
                                   **inbox.status(s), "to_make": my_songs_waiting(s)})
            if path == "/api/inbox/rights":
                inbox.set_rights(s, bool(body.get("confirmed")))
                return self._json(inbox.status(s))
            if path == "/api/schedule/plan":
                return self._plan(s, body)
            if path == "/api/schedule/cancel":
                conn = db.connect(config.resolve(s, "database"))
                if body.get("all"):
                    return self._json({"ok": True, "cancelled": squeue.cancel_all_pending(conn)})
                return self._json({"ok": squeue.cancel(conn, int(body.get("id", 0)))})
            if path == "/api/publish-ready":
                def work_all():
                    conn = db.connect(config.resolve(s, "database"))
                    r = squeue.publish_all_ready(s, conn, say=logging.getLogger("piano").info)
                    return f"{r['published']} publiée(s), {r['failed']} échec(s) sur {r['total']}"
                if not JOB.start_task("publish-all", work_all):
                    return self._json({"error": "une opération est déjà en cours"}, 409)
                return self._json({"ok": True})
            if path == "/api/publish-now":
                return self._publish_now(s, body)
            opt = options(s)
            if path == "/api/week":
                body = {**body, "week": True}
            level = body.get("level") or None
            formats = body.get("formats") or ([body["format"]] if body.get("format") else opt["default_formats"])
            if level not in {l["key"] for l in opt["levels"]} | {None}:
                return self._json({"error": "niveau inconnu"}, 400)
            if not formats or not all(f in {x["key"] for x in opt["formats"]} for f in formats):
                return self._json({"error": "format inconnu"}, 400)
            plan = None
            if body.get("week") and body.get("replace"):                           # le nouvel agenda remplace les publications encore en attente
                squeue.cancel_all_pending(db.connect(config.resolve(s, "database")))
            if body.get("week") and body.get("days") is not None:                  # agenda : nombre de vidéos voulu pour chaque jour
                try:
                    slots = squeue.slots_for_days(body["days"], body.get("times"))
                except (ValueError, KeyError, TypeError):
                    return self._json({"error": "agenda invalide"}, 400)
                if not slots:
                    return self._json({"error": "Choisis au moins une vidéo sur un jour à venir dans l'agenda."}, 400)
                slots = slots[:30]
                plan = {"slots": slots, "immediate": bool(body.get("immediate", False)), "times": squeue.parse_times(body.get("times") or []) or ["12:30", "19:00"]}
                count = len(slots)
                publish = False
            elif body.get("week"):
                try:
                    plan = {"minutes": min(max(float(body.get("minutes", 30) or 30), 5), 600),
                            "per_day": min(max(int(body.get("per_day", 2) or 2), 1), 6),
                            "times": squeue.parse_times(body.get("times") or ["12:30", "19:00"]) or ["12:30", "19:00"],
                            "immediate": bool(body.get("immediate", False)),
                            "first_day": date.fromisoformat(body.get("first_day") or (date.today() + timedelta(days=1)).isoformat())}
                except ValueError:
                    return self._json({"error": "date ou durée invalide"}, 400)
                count = max(1, min(int(body.get("count", 14) or 14), 30))
                publish = False                                   # en mode semaine, rien ne part à la création : tout est programmé
            else:
                count = max(1, min(int(body.get("count", 1) or 1), 5))
                publish = bool(body.get("publish", False))
            if body.get("synthesia", False):
                s = {**s, "style": "synthesia", "engine": "synthesia"}   # Synthesia demandé : une erreur s'affiche, pas de repli silencieux
            elif s.get("style", "sketch") != "synthesia":
                s = {**s, "style": "sketch"}                              # style dessiné (défaut) : aucune app requise
            else:
                s = {**s, "engine": "builtin"}
            if not JOB.start(s, level, formats, publish, count, int(body["song_id"]) if body.get("song_id") and not plan else None,
                         body.get("lang") if body.get("lang") in ("fr", "en", "es") else None, plan):
                return self._json({"error": "une vidéo est déjà en cours de création"}, 409)
            self._json({"ok": True})

    return Handler


def serve(port=8765, open_browser=True, settings_loader=config.load_settings):
    try:
        srv = QuietServer(("127.0.0.1", port), make_handler(settings_loader))
    except OSError as e:
        print(f"❌ Le port {port} est déjà utilisé ({e.strerror}) : une ancienne page tourne encore.\n"
              f"   Fermez-la (Ctrl+C dans son Terminal) ou lancez : lsof -ti tcp:{port} | xargs kill")
        raise SystemExit(1)
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    print(f"Interface Piano Studio AI : {url}   (Ctrl+C pour arrêter)")
    try:                                                 # ancien système : plus aucune publication « programmée dans l'app » ne doit partir
        s0 = settings_loader()
        n = squeue.cancel_all_pending(db.connect(config.resolve(s0, "database")))
        if n:
            print(f"ℹ {n} ancienne(s) publication(s) programmée(s) dans l'app annulée(s) : la programmation se fait maintenant dans TikTok et YouTube.")
    except Exception:
        pass
    try:
        from app.director import cleanup
        s1 = settings_loader()
        cleanup.purge_partial(s1)                          # rendus interrompus par un arrêt brutal
        cn1 = db.connect(config.resolve(s1, "database"))
        cleanup.purge_published(s1, cn1)                   # vidéos déjà publiées restées sur le disque
        cleanup.purge_orphans(s1, cn1)                     # restes d'essais ratés
    except Exception:
        pass
    due_runner(settings_loader)                          # surveillance du dossier MIDI
    stock.refill_in_background(settings_loader())         # réserve de morceaux prête avant même le premier clic
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return srv
