"""Publications programmées : « publie cette vidéo mardi à 19 h » ou « programme toute la semaine ».

Une ligne `schedule` = une vidéo + une heure. À l'heure dite, la vidéo part vers toutes les plateformes prévues pour son format
(`config/platforms.yaml` : vertical -> TikTok + YouTube Shorts, horizontal -> YouTube). L'exécution se fait quand l'interface (`piano ui`)
est ouverte ou via `piano publish-due` ; le Mac doit être allumé, écran actif."""
import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app import config
from app.database import db

log = logging.getLogger("piano.queue")
GOOD = ("PUBLISHED", "DRAFT")


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


def slots_for_days(days, times=None, now: datetime | None = None) -> list[datetime]:
    """Agenda : `days` = [{"date": "2026-10-12", "count": 2}, ...] -> un créneau par vidéo, heures locales. Pour n vidéos le même jour on prend
    les n premières heures de la liste (complétée par des heures par défaut), triées. Les créneaux d'AUJOURD'HUI déjà passés ne sont pas perdus :
    la vidéo part dès que le montage est fini (quelques minutes plus tard, une toutes les 15 minutes). Les jours passés sont ignorés."""
    chosen = parse_times(times) if times else []
    chosen = chosen or DEFAULT_TIMES[:2]
    pool = chosen + [x for x in DEFAULT_TIMES if x not in chosen]
    now = now or datetime.now().astimezone()
    limit = now + timedelta(minutes=10)
    out, late = [], 0
    for d in sorted(days, key=lambda x: x["date"]):
        day = date.fromisoformat(d["date"])
        if day < now.date():
            continue
        n = max(0, min(int(d.get("count", 0)), 6))
        for hhmm in sorted(pool[:n]):
            h, m = (int(x) for x in hhmm.split(":"))
            dt = datetime(day.year, day.month, day.day, h, m).astimezone()
            if dt > limit:
                out.append(dt)
            elif day == now.date():                          # créneau d'aujourd'hui déjà passé : publication dès que prêt
                out.append(now + timedelta(minutes=2 + 15 * late)); late += 1
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
    vids = {v["id"]: v for v in unscheduled(conn)}
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


def publish_video(s, conn, video_id: int) -> list[dict]:
    """Publie une vidéo déjà créée sur les plateformes de son format. Une plateforme en échec ne bloque pas les autres."""
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
    if content.get("thumbnail") and (video.parent / content["thumbnail"]).exists():
        content["thumbnail"] = str(video.parent / content["thumbnail"])
    else:
        content.pop("thumbnail", None)
    s2 = {**s, "tiktok": {**s.get("tiktok", {})}, "youtube": {**s.get("youtube", {})}}
    for plat in ("tiktok", "youtube"):
        if s2[plat].get("mode") == "web":
            s2[plat]["web_publish"] = True                 # « publier » veut dire publier : on clique aussi sur le bouton
    out = []
    for ad in adapters(s2, fmt=fmt):
        if ad.platform == "outbox":
            continue
        try:
            r = ad.publish(video, content, str(video_id))
        except Exception as e:
            r = Result(getattr(ad, "platform", "?"), "FAILED", detail=str(e)[:300])
        conn.execute("INSERT OR REPLACE INTO publications(video_id,platform,post_id,status,published_at) VALUES(?,?,?,?,?)",
                     (video_id, r.platform, r.post_id, r.status, db.now()))
        if r.status == "FAILED":
            db.log_error(conn, f"publish:{r.platform}", r.detail)
        log.info("📤 %s : %s %s", r.platform, r.status, (r.detail or "")[:100])
        out.append({"platform": r.platform, "status": r.status, "detail": r.detail})
    if any(x["status"] in GOOD for x in out):
        conn.execute("UPDATE videos SET status='PUBLISHED' WHERE id=?", (video_id,))
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
