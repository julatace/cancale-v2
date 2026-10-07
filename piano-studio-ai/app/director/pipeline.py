"""Director : une vidéo de bout en bout, déterministe, avec retry et sans jamais bloquer sur une plateforme."""
import logging
import random
import tempfile
from pathlib import Path

from app import config
from app.content_generator.generate import difficulty_of, generate
from app.database import db
from app.midi_analyzer.analyzer import analyze
from app.midi_analyzer.parser import parse_midi
from app.music_discovery import generator, importer
from app.publisher import adapters
from app.quality_control import qc
from app.section_selector.selector import select_section
from app.visualizer import falling

log = logging.getLogger("piano.director")


def pick_song(conn, s, seed) -> tuple[int, Path, dict]:
    """1) MIDI LEGAL_CONFIRMED inutilisé en base ; 2) mélodie du domaine public ; 3) composition originale."""
    rows = conn.execute("SELECT id, midi_path, title, artist FROM songs WHERE license='LEGAL_CONFIRMED' ORDER BY id").fetchall()
    for r in rows:
        if r["midi_path"] and Path(r["midi_path"]).exists() and db.song_usable(conn, r["id"], s["same_song_cooldown_days"])[0]:
            return r["id"], Path(r["midi_path"]), {"title": r["title"], "artist": r["artist"]}
    midi_dir = config.resolve(s, "data_dir") / "midi"
    midi_dir.mkdir(parents=True, exist_ok=True)
    candidates = [lambda: generator.pd_song(n) for n in generator.PD_SONGS] + [lambda: generator.compose(seed)]
    rnd = random.Random(seed)
    rnd.shuffle(candidates[:-1])
    for make in candidates[:-1] + candidates[-1:]:
        data, meta = make()
        f = midi_dir / f"tmp_{seed}.mid"
        f.write_bytes(data)
        r = importer.import_midi(conn, f, meta["title"], meta["artist"], "user_owned", "composition originale / domaine public",
                                 dest_dir=midi_dir)
        f.unlink(missing_ok=True)
        sid = r["song_id"]
        if r["status"] in ("LEGAL_CONFIRMED", "DUPLICATE") and sid and db.song_usable(conn, sid, s["same_song_cooldown_days"])[0]:
            path = conn.execute("SELECT midi_path FROM songs WHERE id=?", (sid,)).fetchone()[0]
            return sid, Path(path), meta
    return pick_song(conn, s, seed + 1000003) if seed < 10_000_000 else (_ for _ in ()).throw(RuntimeError("aucun morceau disponible"))


def run_one(s, seed=None, dry_run=False, publish=True) -> dict:
    conn = db.connect(config.resolve(s, "database"))
    seed = seed if seed is not None else random.SystemRandom().randrange(1, 1_000_000)
    sid, midi, meta = pick_song(conn, s, seed)
    notes, tempo = parse_midi(midi)
    ana = analyze(notes, tempo)
    sec = select_section(notes, min(s["duration_target"], ana["duration"]))
    diff = difficulty_of(ana)
    used = {r[0] for r in conn.execute("SELECT title FROM videos WHERE title IS NOT NULL")}
    content = generate({"title": meta["title"], "artist": meta["artist"]}, diff, seed, used)
    report = {"song": meta["title"], "section": sec, "difficulty": diff, "title": content["title"]}
    if dry_run:
        return {**report, "status": "DRY_RUN"}
    out_dir = config.resolve(s, "data_dir") / "rendered"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{sid}_{seed}.mp4"
    result = None
    for attempt in range(1, 4):
        try:
            falling.render_video(notes, sec["start"], sec["duration"], out, meta["title"], meta["artist"], fps=30)
            result = qc.check(out, dur_range=(3, s["duration_range"][1] + 5))
            if qc.verdict(result["score"], **{"publish_min": s["qc"]["publish_min"], "autofix_min": s["qc"]["autofix_min"]}) == "PUBLISH":
                break
            log.warning("QC %s (tentative %d): %s", result["score"], attempt, result["issues"])
        except Exception as e:
            db.log_error(conn, "render", f"{type(e).__name__}: {e}", retry_count=attempt)
            log.error("rendu échoué (tentative %d): %s", attempt, e)
    ok = result is not None and result["score"] >= s["qc"]["publish_min"]
    vid = conn.execute("INSERT INTO videos(song_id,style,duration,output_path,quality_score,status,title,created_at) VALUES(?,?,?,?,?,?,?,?)",
                       (sid, "viral", sec["duration"], str(out), result["score"] if result else 0,
                        "READY" if ok else "FAILED", content["title"], db.now())).lastrowid
    conn.commit()
    report.update(video=str(out), qc=result, status="READY" if ok else "FAILED", publications=[])
    if ok and publish:
        for ad in adapters(s):
            try:
                r = ad.publish(out, content, f"{vid}")
            except Exception as e:  # une plateforme ne bloque jamais les autres
                from app.publisher.base import Result
                r = Result(getattr(ad, "platform", "?"), "FAILED", detail=str(e)[:200])
            conn.execute("INSERT OR REPLACE INTO publications(video_id,platform,post_id,status,published_at) VALUES(?,?,?,?,?)",
                         (vid, r.platform, r.post_id, r.status, db.now()))
            if r.status == "FAILED":
                db.log_error(conn, f"publish:{r.platform}", r.detail)
            report["publications"].append({"platform": r.platform, "status": r.status, "detail": r.detail})
        if any(x["status"] == "PUBLISHED" for x in report["publications"]):
            conn.execute("UPDATE videos SET status='PUBLISHED' WHERE id=?", (vid,))
            report["status"] = "PUBLISHED"
        conn.commit()
    return report
