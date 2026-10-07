"""Director : une vidéo de bout en bout, déterministe, avec retry et sans jamais bloquer sur une plateforme."""
import logging
import random
import tempfile
import time
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
from app.director import difficulty
from app.visualizer import falling, synth
from app.synthesia_controller import mac, sync
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


def _credit(source: str) -> str:
    return "Mutopia Project (CC BY)" if "CC-BY" in (source or "") else ""


def song_by_id(conn, song_id: int) -> tuple[int, Path, dict]:
    r = conn.execute("SELECT id, midi_path, title, artist, source, license FROM songs WHERE id=?", (song_id,)).fetchone()
    if r is None or r["license"] != "LEGAL_CONFIRMED" or not r["midi_path"] or not Path(r["midi_path"]).exists():
        raise ValueError("morceau introuvable ou non autorisé")
    return r["id"], Path(r["midi_path"]), {"title": r["title"], "artist": r["artist"], "credit": _credit(r["source"])}


def pick_song(conn, s, seed, exclude=()) -> tuple[int, Path, dict]:
    """1) MIDI de la réserve (légal, pas utilisé récemment, tiré au hasard) ; 2) recherche en ligne ; 3) domaine public / composition."""
    rows = conn.execute("SELECT id, midi_path, title, artist, source FROM songs WHERE license='LEGAL_CONFIRMED' ORDER BY id").fetchall()
    ok = [r for r in rows if r["id"] not in exclude and r["midi_path"] and Path(r["midi_path"]).exists()
          and db.song_usable(conn, r["id"], s["same_song_cooldown_days"])[0]]
    if ok:
        r = random.Random(seed).choice(ok)
        return r["id"], Path(r["midi_path"]), {"title": r["title"], "artist": r["artist"], "credit": _credit(r["source"])}
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


def _subtitle(meta, content) -> str:
    lvl = f" · {content['level']} {content['bpm']} BPM" if content.get("level") and content.get("bpm") else ""
    return f"{meta.get('artist', '')}{lvl}".strip(" ·")


def _render(s, notes, sec, out, meta, tempo, content=None, F=None) -> str:
    content = content or {}
    F = F or {"width": 1080, "height": 1920, "banner": 300}
    layout = (F["width"], F["height"], F["banner"])
    """Synthesia (app de l'utilisateur) si disponible, sinon rendu intégré : la production ne s'arrête jamais."""
    cfg = s.get("synthesia", {})
    if s.get("engine", "auto") != "builtin" and mac.ready(cfg):
        try:
            with tempfile.TemporaryDirectory() as td:
                td = Path(td)
                (td / "s.mid").write_bytes(trim_midi(notes, sec["start"], sec["start"] + sec["duration"], bpm=content.get("bpm") or 120))
                cap, crop = mac.record(td / "s.mid", sec["duration"], td / "cap.mov", cfg, layout=layout)
                mac.debug_frames(cap, config.resolve(s, "data_dir") / "debug")
                inside = [n for n in notes if n.end > sec["start"] and n.start < sec["start"] + sec["duration"]]
                first = max(min(n.start for n in inside) - sec["start"], 0.0)       # 1re note dans le MIDI découpé
                t_on = sync.detect_first_note(cap, crop, cfg["capture_trim"])
                if t_on is None:
                    t_on = cfg.get("first_note_seconds", 2.5)
                    log.warning("calage auto impossible -> repli sur %.1fs", t_on)
                else:
                    log.info("🎚 Calage du son : 1re note visible à %.1fs dans la vidéo", t_on)
                shift = t_on - first
                shifted = [type(n)(n.start - sec["start"] + shift, n.end - sec["start"] + shift, n.pitch, n.velocity, n.track)
                           for n in inside]
                synth.write_wav(td / "a.wav", synth.render_audio(shifted, 0, sec["duration"]))
                compose.compose_vertical(cap, td / "a.wav", out, cfg["capture_trim"], sec["duration"], meta["title"],
                                       subtitle=_subtitle(meta, content), hook=content.get("hook", ""), cta=content.get("cta", ""), crop=crop,
                                       size=(F["width"], F["height"]), top=F["banner"])
            return "synthesia"
        except Exception as e:
            if s.get("engine") == "synthesia":
                raise                                   # mode forcé : on veut voir l'erreur, pas de repli silencieux
            log.error("Synthesia a échoué (%s) -> rendu intégré", e)
    elif s.get("engine") == "synthesia":
        raise RuntimeError("engine=synthesia mais le Mac n'est pas prêt")
    kb = s["keyboard"]
    falling.render_video(notes, sec["start"], sec["duration"], out, meta["title"], _subtitle(meta, content), fps=30,
                         key_range=(kb["lowest_key"], kb["lowest_key"] + kb["keys"] - 1),
                         layout=falling.HORIZONTAL if F["width"] > F["height"] else falling.VERTICAL)
    return "builtin"


def _target(F, s, ana) -> float:
    if F.get("duration") == "full":
        return min(F.get("max_duration", 300), ana["duration"])
    return min(s["duration_target"], ana["duration"])


def _formats(s, fmt, formats) -> list[tuple[str, dict]]:
    names = list(formats) if formats else [fmt or s.get("default_format", "vertical")]
    fm = s.get("formats", {})
    return [(n, fm.get(n) or {"width": 1080, "height": 1920, "banner": 300, "shorts": True}) for n in names]


def run_one(s, seed=None, dry_run=False, publish=True, level=None, fmt=None, formats=None, song_id=None) -> dict:
    """Une création : UN morceau et UN niveau, rendus dans chaque format demandé (vertical court et/ou horizontal long)."""
    conn = db.connect(config.resolve(s, "database"))
    seed = seed if seed is not None else random.SystemRandom().randrange(1, 1_000_000)
    fmts = _formats(s, fmt, formats)
    log.info("▶ Nouvelle création : recherche d'un morceau libre de droits...")
    done = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    level, lv = difficulty.choose_level(s, done, level)
    needs_full = any(F.get("duration") == "full" for _, F in fmts)
    log.info("🎯 Niveau : %s (%s BPM) | Formats : %s", lv["label"], lv["bpm"], ", ".join(n for n, _ in fmts))
    tried = set()
    for attempt_song in range(6):                   # on écarte les morceaux trop denses / trop courts pour la demande
        sid, midi, meta = song_by_id(conn, song_id) if song_id else pick_song(conn, s, seed + attempt_song * 7919, exclude=tried)
        tried.add(sid)
        log.info("♪ Morceau choisi : %s - %s", meta["title"], meta["artist"])
        notes, tempo = parse_midi(midi)
        notes = fold_notes(notes, s["keyboard"]["lowest_key"], s["keyboard"]["keys"])  # plage du clavier
        factor = difficulty.speed_factor(analyze(notes, tempo)["bpm"], lv["bpm"])
        notes = difficulty.stretch_notes(notes, factor)                                  # tempo = niveau
        tempo = [(0.0, lv["bpm"])]
        ana = analyze(notes, tempo)
        log.info("🔎 Analyse : %s notes, durée %ss (tempo x%.2f -> %s BPM)", ana["note_count"], ana["duration"], factor, lv["bpm"])
        first_sec = select_section(notes, _target(fmts[0][1], s, ana))
        too_short = needs_full and ana["duration"] < min(F.get("min_duration", 90) for _, F in fmts if F.get("duration") == "full")
        if song_id:
            if too_short or first_sec["density"] > lv["max_density"]:
                log.warning("⚠ Morceau choisi par vous : utilisé tel quel, même s'il est %s pour ce niveau/format",
                            "trop court" if too_short else "dense")
            break                                   # morceau imposé : pas de remplacement
        if first_sec["density"] <= lv["max_density"] and not too_short:
            break
        log.info("↻ Morceau écarté (%s) : autre morceau",
                 f"trop court {ana['duration']:.0f}s" if too_short else f"trop dense {first_sec['density']:.1f} notes/s")
    song = {"title": meta["title"], "artist": meta["artist"]}
    used = {r[0] for r in conn.execute("SELECT title FROM videos WHERE title IS NOT NULL")}
    diff = lv["label"]
    reports = []
    for k, (fmt_name, F) in enumerate(fmts):
        sec = select_section(notes, _target(F, s, ana))
        log.info("✂ [%s] Passage retenu : %ss → %ss (%s)", fmt_name, sec["start"], sec["end"], sec["reason"])
        content = generate(song, diff, seed + k, used, lv["bpm"])
        content["format"], content["shorts"] = fmt_name, bool(F.get("shorts", True))
        used.add(content["title"])
        if meta.get("credit"):
            content["description"] += f"\n\nMIDI : {meta['credit']}"
        log.info("✍ [%s] Titre : %s", fmt_name, content["title"])
        report = {"song": meta["title"], "section": sec, "difficulty": diff, "bpm": lv["bpm"], "format": fmt_name, "title": content["title"]}
        if dry_run:
            reports.append({**report, "status": "DRY_RUN"})
            break
        reports.append(_produce(s, conn, sid, level, fmt_name, F, notes, tempo, sec, meta, content, report, publish))
    if len(reports) == 1:
        return reports[0]
    ok = [r["status"] in ("READY", "PUBLISHED") for r in reports]
    return {"song": meta["title"], "difficulty": diff, "bpm": lv["bpm"], "videos": reports,
            "status": "READY" if all(ok) else "PARTIAL" if any(ok) else "FAILED"}


def _produce(s, conn, sid, level, fmt_name, F, notes, tempo, sec, meta, content, report, publish) -> dict:
    full = F.get("duration") == "full"
    out_dir = config.resolve(s, "data_dir") / "rendered"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{sid}_{int(time.time())}_{fmt_name}.mp4"
    result, last_err = None, ""
    for attempt in range(1, 4):
        try:
            log.info("🎬 [%s] Fabrication de la vidéo (tentative %d/3)...", fmt_name, attempt)
            engine = _render(s, notes, sec, out, meta, tempo, content, F)
            report["engine"] = engine
            log.info("🎬 [%s] Vidéo prête avec le moteur « %s »", fmt_name, engine)
            log.info("✔ Contrôle qualité...")
            dur_range = (min(30, F.get("max_duration", 300) * 0.5), F.get("max_duration", 300) + 10) if full else (3, s["duration_range"][1] + 5)
            result = qc.check(out, expect_w=F["width"], expect_h=F["height"], dur_range=dur_range)
            if qc.verdict(result["score"], publish_min=s["qc"]["publish_min"], autofix_min=s["qc"]["autofix_min"]) == "PUBLISH":
                break
            log.warning("QC %s (tentative %d): %s", result["score"], attempt, result["issues"])
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            db.log_error(conn, "render", last_err, retry_count=attempt)
            log.error("rendu échoué (tentative %d): %s", attempt, e)
            if s.get("engine") == "synthesia":
                break                                   # mode forcé : une seule tentative, on veut l'erreur
    ok = result is not None and result["score"] >= s["qc"]["publish_min"]
    log.info("✔ [%s] Score qualité : %s/100 -> %s", fmt_name, result["score"] if result else 0, "OK" if ok else "REFUSÉE")
    vid = conn.execute("INSERT INTO videos(song_id,style,duration,output_path,quality_score,status,title,created_at) VALUES(?,?,?,?,?,?,?,?)",
                       (sid, f"{level}|{fmt_name}", sec["duration"], str(out), result["score"] if result else 0,
                        "READY" if ok else "FAILED", content["title"], db.now())).lastrowid
    conn.commit()
    report.update(video=str(out), qc=result, status="READY" if ok else "FAILED", publications=[])
    if last_err and not ok:
        report["error"] = last_err
        log.error("✖ ÉCHEC : %s", last_err)
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
