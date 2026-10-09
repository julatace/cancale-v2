"""Publications programmées : « publie cette vidéo mardi à 19 h » ou « programme toute la semaine ».

Une ligne `schedule` = une vidéo + une heure. À l'heure dite, la vidéo part vers toutes les plateformes prévues pour son format
(`config/platforms.yaml` : vertical -> TikTok + YouTube Shorts, horizontal -> YouTube). L'exécution se fait quand l'interface (`piano ui`)
est ouverte ou via `piano publish-due` ; le Mac doit être allumé, écran actif."""
import json
import threading
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app import config
from app.database import db

log = logging.getLogger("piano.queue")
SEND_LOCK = threading.Lock()                                      # un seul envoi à la fois dans toute l'app (jamais deux envois en parallèle)
AMBIGUOUS = ("n'a pas confirmé", "interrompu")                    # échec APRÈS le dernier clic : la vidéo est peut-être déjà en ligne


def record_manual(conn, video_id: int, platform: str, status: str, detail: str = "") -> None:
    """Trace un envoi fait à la main (./p.sh tiktok-web, youtube-web) : l'app ne le refera jamais."""
    conn.execute("INSERT OR REPLACE INTO publications(video_id,platform,post_id,status,published_at) VALUES(?,?,?,?,?)", (video_id, platform, detail[:200], status, db.now()))
    if status in GOOD:
        conn.execute("UPDATE videos SET status='PUBLISHED' WHERE id=?", (video_id,))
    conn.commit()

GOOD = ("PUBLISHED", "DRAFT", "SCHEDULED")                       # SCHEDULED = programmée DANS le réseau (TikTok / YouTube la mettront en ligne à l'heure)
MIN_LEAD_MIN, MAX_LEAD_DAYS = 20, 10                              # TikTok : programmation de 15 min à 10 jours à l'avance


def parse_times(times) -> list[str]:
    """« 12:30, 19h » -> ['12:30', '19:00'] ; ignore ce qui n'est pas une heure."""
    if isinstance(times, str):
        times = times.replace(";", ",").split(",")
    out = []
    for t in times:
        t = str(t).strip().lower().replace("h", ":")
        if t.endswith(":"):
            t += "00"
        try:
            h, m = (int(x) for x in t.split(":")[:2])
        except ValueError:
            continue
        if 0 <= h < 24 and 0 <= m < 60 and f"{h:02d}:{m:02d}" not in out:
            out.append(f"{h:02d}:{m:02d}")
    return sorted(out)


def slots(first_day: date, count: int, per_day: int, times, now: datetime | None = None) -> list[datetime]:
    """`count` créneaux (heure locale) à partir de `first_day`, `per_day` par jour aux heures données ; le passé est ignoré."""
    times = parse_times(times) or ["12:30", "19:00"]
    times = times[:max(1, per_day)]
    now = (now or datetime.now().astimezone()) + timedelta(minutes=10)
    first_day = max(first_day, now.date())                          # un premier jour déjà passé démarre aujourd'hui
    out, day = [], first_day
    while len(out) < count and (day - first_day).days < 120:
        for t in times:
            h, m = (int(x) for x in t.split(":"))
            dt = datetime(day.year, day.month, day.day, h, m).astimezone()          # heure locale du Mac
            if dt > now and len(out) < count:
                out.append(dt)
        day += timedelta(days=1)
    return out


DEFAULT_TIMES = ["12:30", "19:00", "09:00", "16:00", "21:00", "11:00"]


class SlotError(RuntimeError):
    """Créneau impossible à confier aux réseaux (trop lointain pour TikTok)."""


def slots_for_days(days, times=None, now: datetime | None = None) -> list[datetime]:
    """Agenda : `days` = [{"date": "2026-10-12", "count": 2}, ...] -> un créneau par vidéo, heures locales, toujours dans le FUTUR.
    Pour n vidéos le même jour : d'abord tes heures, puis des heures par défaut (09:00, 11:00, 12:30, 16:00, 19:00, 21:00). Une heure déjà passée
    (ou à moins de 30 min) est sautée ; ce qui ne tient plus aujourd'hui passe au jour suivant. Maximum 10 jours (limite de TikTok)."""
    chosen = parse_times(times) if times else []
    chosen = chosen or DEFAULT_TIMES[:2]
    order = chosen + [x for x in DEFAULT_TIMES if x not in chosen]
    now = now or datetime.now().astimezone()
    limit = now + timedelta(minutes=MIN_LEAD_MIN + 10)
    horizon = now + timedelta(days=MAX_LEAD_DAYS)
    wanted = {d["date"]: max(0, min(int(d.get("count", 0)), 6)) for d in days}
    out, carry = [], 0
    for offset in range(MAX_LEAD_DAYS + 1):
        day = now.date() + timedelta(days=offset)
        n = wanted.get(day.isoformat(), 0) + carry
        carry = 0
        if n <= 0:
            continue
        picks = []
        for hhmm in order:
            h, m = (int(x) for x in hhmm.split(":"))
            dt = datetime(day.year, day.month, day.day, h, m).astimezone()
            if limit < dt <= horizon:
                picks.append(dt)
            if len(picks) == n:
                break
        carry = n - len(picks)
        out += sorted(picks)
    return sorted(out)


def _utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def unscheduled(conn) -> list[dict]:
    """Vidéos prêtes qui ne sont ni programmées ni publiées."""
    rows = conn.execute(
        "SELECT v.id, v.song_id, v.title, v.style FROM videos v WHERE v.status='READY' AND NOT EXISTS "
        "(SELECT 1 FROM schedule s WHERE s.video_id=v.id AND s.status IN ('PENDING','RUNNING','DONE')) ORDER BY v.id").fetchall()
    return [{"id": r["id"], "song_id": r["song_id"], "title": r["title"], "format": (r["style"] or "").partition("|")[2]} for r in rows]


def plan(conn, video_ids, when: list[datetime]) -> list[dict]:
    """Une vidéo courte et sa version longue (même morceau) partent ensemble, au même créneau."""
    vids = {v["id"]: v for v in unscheduled(conn)}                   # (déjà limité par l'appelant aux vidéos de la dernière fabrication)
    groups: dict[object, list[dict]] = {}
    for vid in video_ids:
        v = vids.get(int(vid))
        if v:
            groups.setdefault(v["song_id"] or f"v{v['id']}", []).append(v)
    out = []
    for grp, dt in zip(groups.values(), when):
        for v in grp:
            conn.execute("INSERT INTO schedule(video_id,run_at,status,created_at) VALUES(?,?,'PENDING',?)", (v["id"], _utc(dt), db.now()))
            out.append({"video_id": v["id"], "title": v["title"], "format": v["format"], "run_at": dt.isoformat(timespec="minutes")})
    conn.commit()
    return out


def assign(conn, video_ids, when) -> list[tuple[int, datetime]]:
    """Associe chaque vidéo prête à un créneau (la version courte et la version longue d'un même morceau partagent le même créneau)."""
    marks = ",".join("?" * len(video_ids)) or "NULL"
    rows = conn.execute(f"SELECT id, song_id FROM videos WHERE id IN ({marks}) AND status='READY' ORDER BY id", [int(i) for i in video_ids]).fetchall()
    groups: dict[object, list[int]] = {}
    for r in rows:
        groups.setdefault(r["song_id"] or f"v{r['id']}", []).append(r["id"])
    return [(vid, dt) for grp, dt in zip(groups.values(), when) for vid in grp]


def drop_orphans(conn) -> int:
    """Retire les anciennes lignes « en attente » devenues sans objet : vidéo déjà publiée, ou fichier supprimé."""
    n = 0
    for r in conn.execute("SELECT s.id, v.status, v.output_path FROM schedule s LEFT JOIN videos v ON v.id=s.video_id WHERE s.status='PENDING'").fetchall():
        if r["status"] != "READY" or not r["output_path"] or not Path(r["output_path"]).exists():
            conn.execute("UPDATE schedule SET status='CANCELLED' WHERE id=?", (r["id"],)); n += 1
    conn.commit()
    return n


def listing(conn, limit=40) -> list[dict]:
    rows = conn.execute("SELECT s.id, s.video_id, s.run_at, s.status, s.detail, v.title, v.style FROM schedule s LEFT JOIN videos v ON v.id=s.video_id "
                        "WHERE s.status!='CANCELLED' ORDER BY s.run_at DESC LIMIT ?", (limit,)).fetchall()
    out = []
    for r in rows:
        local = datetime.fromisoformat(r["run_at"]).astimezone()
        out.append({"id": r["id"], "video_id": r["video_id"], "title": r["title"], "format": (r["style"] or "").partition("|")[2],
                    "run_at": local.isoformat(timespec="minutes"), "status": r["status"], "detail": r["detail"] or ""})
    return sorted(out, key=lambda x: x["run_at"])


def cancel(conn, schedule_id: int) -> bool:
    cur = conn.execute("UPDATE schedule SET status='CANCELLED' WHERE id=? AND status='PENDING'", (int(schedule_id),))
    conn.commit()
    return cur.rowcount > 0


BATCH_FILE = config.ROOT / "data" / "last_batch.json"        # vidéos de la DERNIÈRE fabrication (les seules que les boutons « envoyer les vidéos prêtes » touchent)


def set_last_batch(ids) -> None:
    BATCH_FILE.parent.mkdir(parents=True, exist_ok=True)
    BATCH_FILE.write_text(json.dumps([int(i) for i in ids]))


def last_batch() -> list[int] | None:
    try:
        return [int(i) for i in json.loads(BATCH_FILE.read_text())]
    except Exception:
        return None


def ready_videos(conn, everything: bool = False) -> list[dict]:
    """Vidéos montées, pas encore publiées, dont le fichier existe encore, de la DERNIÈRE fabrication seulement (jamais les anciennes).
    Sans trace de la dernière fabrication : celles montées dans les 3 heures qui précèdent la plus récente."""
    rows = conn.execute("SELECT id, title, style, output_path, created_at FROM videos WHERE status='READY' ORDER BY id").fetchall()
    rows = [r for r in rows if r["output_path"] and Path(r["output_path"]).exists()]
    if not everything:
        batch = last_batch()
        if batch is not None:
            rows = [r for r in rows if r["id"] in set(batch)]
        elif rows:
            newest = datetime.fromisoformat(rows[-1]["created_at"])
            rows = [r for r in rows if newest - datetime.fromisoformat(r["created_at"]) <= timedelta(hours=3)]
    return [{"id": r["id"], "title": r["title"], "format": (r["style"] or "").partition("|")[2]} for r in rows]


def publish_all_ready(s, conn, say=log.info, publish=None) -> dict:
    """Publie tout de suite, l'une après l'autre, toutes les vidéos prêtes. Leurs heures programmées sont retirées (pas de double publication)."""
    publish = publish or publish_video
    vids = ready_videos(conn)
    ok = fail = 0
    from app.director import control
    for i, v in enumerate(vids, 1):
        control.check()                                    # « Annuler » stoppe avant la vidéo suivante
        conn.execute("UPDATE schedule SET status='CANCELLED' WHERE video_id=? AND status='PENDING'", (v["id"],))
        conn.commit()
        say(f"🚀 [{i}/{len(vids)}] Publication de « {(v['title'] or '')[:60]} » ({v['format'] or '?'})…")
        try:
            res = publish(s, conn, v["id"])
            good = any(x["status"] in GOOD for x in res)
        except Exception as e:
            say(f"✖ Publication impossible : {e}")
            good = False
        ok += good
        fail += not good
    return {"published": ok, "failed": fail, "total": len(vids)}


def cancel_all_pending(conn) -> int:
    """Annule toutes les publications en attente (les vidéos restent, seules les heures sont retirées)."""
    cur = conn.execute("UPDATE schedule SET status='CANCELLED' WHERE status='PENDING'")
    conn.commit()
    return cur.rowcount


def native_time(publish_at, now: datetime | None = None):
    """Heure à confier à TikTok / YouTube (leur programmation), ou None = publier tout de suite (seulement si aucune date n'est demandée).
    Une heure trop proche est avancée au plus tôt possible ; trop lointaine (plus de 10 jours) : SlotError, rien n'est publié."""
    if not publish_at:
        return None
    dt = publish_at if isinstance(publish_at, datetime) else datetime.fromisoformat(str(publish_at))
    dt = dt.astimezone()
    now = now or datetime.now().astimezone()
    if dt < now + timedelta(minutes=MIN_LEAD_MIN):
        dt = now + timedelta(minutes=MIN_LEAD_MIN + 5)
    if dt > now + timedelta(days=MAX_LEAD_DAYS):
        raise SlotError(f"{dt:%d/%m %H:%M} est trop loin : TikTok programme au maximum {MAX_LEAD_DAYS} jours à l'avance")
    return dt


def publish_video(s, conn, video_id: int, publish_at=None) -> list[dict]:
    """Envoie une vidéo déjà créée aux réseaux de son format. Avec `publish_at`, chaque réseau la PROGRAMME lui-même à cette date et heure
    (TikTok Studio « Planifier », YouTube Studio « Programmer »). Une plateforme en échec ne bloque pas les autres, et un nouvel appel ne
    refait que ce qui a échoué."""
    from app.publisher import adapters
    from app.publisher.base import Result
    row = conn.execute("SELECT output_path, style, meta FROM videos WHERE id=?", (int(video_id),)).fetchone()
    if row is None:
        raise RuntimeError(f"vidéo {video_id} introuvable")
    video = Path(row["output_path"] or "")
    if not video.exists():
        raise RuntimeError(f"fichier vidéo absent : {video.name}")
    fmt = (row["style"] or "").partition("|")[2] or None
    content = json.loads(row["meta"] or "{}")
    content["shorts"] = fmt != "horizontal"                # la vidéo horizontale est une vidéo YouTube normale, pas un Short
    try:
        when = native_time(publish_at)
    except SlotError as e:
        return [{"platform": "agenda", "status": "FAILED", "detail": str(e)}]      # rien n'est envoyé, la vidéo reste prête
    if when:
        content["publish_at"] = when.replace(tzinfo=None).isoformat(timespec="minutes")     # heure locale du Mac, telle qu'affichée dans les réseaux
    if content.get("thumbnail") and (video.parent / content["thumbnail"]).exists():
        content["thumbnail"] = str(video.parent / content["thumbnail"])
    else:
        content.pop("thumbnail", None)
    s2 = {**s, "tiktok": {**s.get("tiktok", {})}, "youtube": {**s.get("youtube", {})}}
    for plat in ("tiktok", "youtube"):
        if s2[plat].get("mode") == "web":
            s2[plat]["web_publish"] = True                 # « publier » veut dire publier : on clique aussi sur le bouton
    done = {r["platform"]: r["status"] for r in conn.execute("SELECT platform, status FROM publications WHERE video_id=?", (video_id,))}
    if not SEND_LOCK.acquire(blocking=False):
        return [{"platform": "app", "status": "FAILED", "detail": "un autre envoi est déjà en cours : rien n'a été renvoyé"}]
    try:
        out = []
        for ad in adapters(s2, fmt=fmt):
            if ad.platform == "outbox":
                continue
            if done.get(ad.platform) in GOOD:              # déjà parti sur ce réseau : on ne le refait pas
                out.append({"platform": ad.platform, "status": done[ad.platform], "detail": "déjà envoyé"})
                continue
            if done.get(ad.platform) in ("SENDING", "UNCERTAIN"):      # envoi interrompu / non confirmé : peut déjà être en ligne, donc JAMAIS renvoyé tout seul
                out.append({"platform": ad.platform, "status": "UNCERTAIN",
                            "detail": f"envoi non confirmé : regarde dans {ad.platform} si la vidéo y est avant de réessayer (renvoyer risquerait un doublon)"})
                continue
            conn.execute("INSERT OR REPLACE INTO publications(video_id,platform,post_id,status,published_at) VALUES(?,?,?,?,?)",
                         (video_id, ad.platform, "", "SENDING", db.now()))                 # « envoi en cours » : survit à un arrêt brutal de l'app
            conn.commit()
            try:
                r = ad.publish(video, content, str(video_id))
            except Exception as e:
                r = Result(getattr(ad, "platform", "?"), "FAILED", detail=str(e)[:300])
            if r.status == "FAILED" and any(m in (r.detail or "") for m in AMBIGUOUS):
                r = Result(r.platform, "UNCERTAIN", r.post_id, r.detail)
            conn.execute("INSERT OR REPLACE INTO publications(video_id,platform,post_id,status,published_at) VALUES(?,?,?,?,?)",
                         (video_id, r.platform, r.post_id, r.status, db.now()))
            if r.status in ("FAILED", "UNCERTAIN"):
                db.log_error(conn, f"publish:{r.platform}", r.detail)
            conn.commit()
            log.info("📤 %s : %s %s", r.platform, r.status, (r.detail or "")[:100])
            out.append({"platform": r.platform, "status": r.status, "detail": r.detail})
    finally:
        SEND_LOCK.release()
    if any(x["status"] in GOOD for x in out):
        conn.execute("UPDATE videos SET status='PUBLISHED' WHERE id=?", (video_id,))
    if when:                                               # trace dans « Programmation » : ce qui est programmé DANS les réseaux
        ok_names = ", ".join(x["platform"] for x in out if x["status"] in GOOD)
        bad = [x for x in out if x["status"] not in GOOD]
        conn.execute("INSERT INTO schedule(video_id,run_at,status,detail,created_at) VALUES(?,?,?,?,?)",
                     (video_id, _utc(when), "DONE" if ok_names and not bad else "FAILED",
                      (f"programmée dans {ok_names}" if ok_names else "") + ("; " if ok_names and bad else "") +
                      ("; ".join(f"{x['platform']} : {x['detail'][:80]}" for x in bad)), db.now()))
    conn.commit()
    from app.director import cleanup
    cleanup.delete_after_publish(s, conn, video_id, out)                  # tout est parti : on libère la place sur l'ordinateur
    return out


def run_due(s, conn, now: datetime | None = None, publish=publish_video, late_hours: float = 12) -> list[dict]:
    """Publie, dans l'ordre, tout ce dont l'heure est passée. Trop en retard (Mac éteint…) = « MISSED », jamais publié par surprise."""
    now = now or datetime.now(timezone.utc)
    rows = conn.execute("SELECT id, video_id, run_at FROM schedule WHERE status='PENDING' AND run_at<=? ORDER BY run_at", (_utc(now),)).fetchall()
    done = []
    for r in rows:
        if now - datetime.fromisoformat(r["run_at"]) > timedelta(hours=late_hours):
            conn.execute("UPDATE schedule SET status='MISSED', detail=? WHERE id=?", ("heure dépassée de plus de %g h : republie-la à la main" % late_hours, r["id"]))
            conn.commit()
            done.append({"id": r["id"], "status": "MISSED"})
            continue
        conn.execute("UPDATE schedule SET status='RUNNING' WHERE id=?", (r["id"],))
        conn.commit()
        try:
            res = publish(s, conn, r["video_id"])
            ok = any(x["status"] in GOOD for x in res)
            detail = " ; ".join(f"{x['platform']}: {x['status']}" + (f" ({x['detail'][:80]})" if x["status"] == "FAILED" else "") for x in res)
        except Exception as e:
            ok, detail = False, str(e)[:300]
        conn.execute("UPDATE schedule SET status=?, detail=? WHERE id=?", ("DONE" if ok else "FAILED", detail, r["id"]))
        conn.commit()
        done.append({"id": r["id"], "video_id": r["video_id"], "status": "DONE" if ok else "FAILED", "detail": detail})
    return done
