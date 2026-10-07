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
from app.midi_analyzer.fold import fold_notes
from app.music_discovery import generator, importer
from app.publisher import adapters
from app.quality_control import qc
from app.section_selector.selector import select_section
from app.visualizer import falling, synth
from app.synthesia_controller import mac
from app.renderer import compose
from app.midi_analyzer.writer import trim_midi

log = logging.getLogger("piano.director")


def _from_mutopia(conn, s, midi_dir, seed):
    """Cherche un nouveau MIDI libre de droits en ligne ; toute erreur réseau = repli silencieux sur les autres sources."""
    if not s.get("midi_sources", {}).get("mutopia", False):
        return None
    from app.music_discovery import mutopia
    try:
        res = mutopia.fetch_one(rnd=random.Random(seed), debug=log.info)
        if not res:
            return None
        info, data = res
        f = midi_dir / f"mutopia_{seed}.mid"
        f.write_bytes(data)
        r = importer.import_midi(conn, f, info["title"], info["composer"], "public_domain",
                                 f"Mutopia {info['license']} {info['page']}", dest_dir=midi_dir)
        f.unlink(missing_ok=True)
        sid = r["song_id"]
        if r["status"] == "LEGAL_CONFIRMED" and sid and db.song_usable(conn, sid, s["same_song_cooldown_days"])[0]:
            path = conn.execute("SELECT midi_path FROM songs WHERE id=?", (sid,)).fetchone()[0]
            return sid, Path(path), {"title": info["title"], "artist": info["composer"], "credit": info["credit"]}
    except Exception as e:
        db.log_error(conn, "mutopia", f"{type(e).__name__}: {str(e)[:150]}", "WARNING")
        log.warning("Mutopia indisponible (%s) -> sources locales", e)
    return None


def pick_song(conn, s, seed) -> tuple[int, Path, dict]:
    """1) MIDI LEGAL_CONFIRMED inutilisé en base ; 2) mélodie du domaine public ; 3) composition originale."""
    rows = conn.execute("SELECT id, midi_path, title, artist FROM songs WHERE license='LEGAL_CONFIRMED' ORDER BY id").fetchall()
    for r in rows:
        if r["midi_path"] and Path(r["midi_path"]).exists() and db.song_usable(conn, r["id"], s["same_song_cooldown_days"])[0]:
            return r["id"], Path(r["midi_path"]), {"title": r["title"], "artist": r["artist"]}
    midi_dir = config.resolve(s, "data_dir") / "midi"
    midi_dir.mkdir(parents=True, exist_ok=True)
    got = _from_mutopia(conn, s, midi_dir, seed)
    if got:
        return got
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


def _render(s, notes, sec, out, meta, tempo, content=None) -> str:
    content = content or {}
    """Synthesia (app de l'utilisateur) si disponible, sinon rendu intégré : la production ne s'arrête jamais."""
    cfg = s.get("synthesia", {})
    if s.get("engine", "auto") != "builtin" and mac.ready(cfg):
        try:
            with tempfile.TemporaryDirectory() as td:
                td = Path(td)
                (td / "s.mid").write_bytes(trim_midi(notes, sec["start"], sec["start"] + sec["duration"]))
                cap, crop = mac.record(td / "s.mid", sec["duration"], td / "cap.mp4", cfg)
                mac.debug_frames(cap, config.resolve(s, "data_dir") / "debug")
                shifted = [type(n)(n.start - sec["start"] + cfg["lead_in_seconds"] - cfg["capture_trim"], n.end - sec["start"] + cfg["lead_in_seconds"] - cfg["capture_trim"], n.pitch, n.velocity, n.track)
                           for n in notes if n.end > sec["start"] and n.start < sec["start"] + sec["duration"]]
                shifted = [n for n in shifted if n.end > 0]
                synth.write_wav(td / "a.wav", synth.render_audio(shifted, 0, sec["duration"]))
                compose.compose_vertical(cap, td / "a.wav", out, cfg["capture_trim"], sec["duration"], meta["title"],
                                       subtitle=meta.get("artist", ""), hook=content.get("hook", ""), cta=content.get("cta", ""), crop=crop)
            return "synthesia"
        except Exception as e:
            log.error("Synthesia a échoué (%s) -> rendu intégré", e)
    elif s.get("engine") == "synthesia":
        raise RuntimeError("engine=synthesia mais le Mac n'est pas prêt")
    kb = s["keyboard"]
    falling.render_video(notes, sec["start"], sec["duration"], out, meta["title"], meta["artist"], fps=30,
                         key_range=(kb["lowest_key"], kb["lowest_key"] + kb["keys"] - 1))
    return "builtin"


def run_one(s, seed=None, dry_run=False, publish=True) -> dict:
    conn = db.connect(config.resolve(s, "database"))
    seed = seed if seed is not None else random.SystemRandom().randrange(1, 1_000_000)
    log.info("▶ Nouvelle vidéo : recherche d'un morceau libre de droits...")
    sid, midi, meta = pick_song(conn, s, seed)
    log.info("♪ Morceau choisi : %s - %s", meta["title"], meta["artist"])
    notes, tempo = parse_midi(midi)
    notes = fold_notes(notes, s["keyboard"]["lowest_key"], s["keyboard"]["keys"])  # clavier 28 touches
    ana = analyze(notes, tempo)
    log.info("🔎 Analyse : %s notes, %s BPM, durée %ss", ana["note_count"], ana["bpm"], ana["duration"])
    sec = select_section(notes, min(s["duration_target"], ana["duration"]))
    log.info("✂ Passage retenu : %ss → %ss (%s)", sec["start"], sec["end"], sec["reason"])
    diff = difficulty_of(ana)
    used = {r[0] for r in conn.execute("SELECT title FROM videos WHERE title IS NOT NULL")}
    content = generate({"title": meta["title"], "artist": meta["artist"]}, diff, seed, used)
    log.info("✍ Titre : %s | niveau %s", content["title"], diff)
    if meta.get("credit"):
        content["description"] += f"\n\nMIDI : {meta['credit']}"
    report = {"song": meta["title"], "section": sec, "difficulty": diff, "title": content["title"]}
    if dry_run:
        return {**report, "status": "DRY_RUN"}
    out_dir = config.resolve(s, "data_dir") / "rendered"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{sid}_{seed}.mp4"
    result = None
    report = {**report}
    for attempt in range(1, 4):
        try:
            log.info("🎬 Fabrication de la vidéo (tentative %d/3)...", attempt)
            engine = _render(s, notes, sec, out, meta, tempo, content)
            report["engine"] = engine
            log.info("🎬 Vidéo prête avec le moteur « %s »", engine)
            log.info("✔ Contrôle qualité...")
            result = qc.check(out, dur_range=(3, s["duration_range"][1] + 5))
            if qc.verdict(result["score"], **{"publish_min": s["qc"]["publish_min"], "autofix_min": s["qc"]["autofix_min"]}) == "PUBLISH":
                break
            log.warning("QC %s (tentative %d): %s", result["score"], attempt, result["issues"])
        except Exception as e:
            db.log_error(conn, "render", f"{type(e).__name__}: {e}", retry_count=attempt)
            log.error("rendu échoué (tentative %d): %s", attempt, e)
    ok = result is not None and result["score"] >= s["qc"]["publish_min"]
    log.info("✔ Score qualité : %s/100 -> %s", result["score"] if result else 0, "OK" if ok else "REFUSÉE")
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
            log.info("📤 %s : %s %s", r.platform, r.status, r.detail[:80])
        if any(x["status"] == "PUBLISHED" for x in report["publications"]):
            conn.execute("UPDATE videos SET status='PUBLISHED' WHERE id=?", (vid,))
            report["status"] = "PUBLISHED"
        conn.commit()
    return report
