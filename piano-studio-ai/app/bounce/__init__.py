"""Agent « rebonds » : vidéos satisfaisantes d'une balle qui rebondit de plateforme en plateforme, une note à chaque impact.
Même autonomie que le piano : choisit un morceau (tes fichiers MIDI), fabrique la vidéo, contrôle, miniature, puis l'agenda et la publication
(TikTok puis YouTube, programmés) s'en occupent comme d'habitude."""
import logging
import random
import re
import time
from pathlib import Path

from app import config
from app.database import db
from app.director import control, pipeline
from app.midi_analyzer.analyzer import analyze
from app.midi_analyzer.arrange import arrange_for_piano
from app.midi_analyzer.parser import parse_midi, parse_midi_info
from app.quality_control import qc
from app.section_selector.hook import select_hook
from . import choreo, content as _content

log = logging.getLogger("piano.bounce")
VERTICAL = {"width": 1080, "height": 1920, "banner": 0}


def is_bounce(s) -> bool:
    return (s.get("agent") or {}).get("kind") == "bounce"


def wanted(s) -> tuple[bool, bool]:
    """(piano, billes) : ce que l'utilisateur veut fabriquer. Au moins un des deux ; l'ancien réglage bounce.with_piano reste compris."""
    pr = s.get("produce") or {}
    piano = bool(pr.get("piano", True))
    bn = bool(pr["bounce"]) if "bounce" in pr else bool((s.get("bounce") or {}).get("with_piano", False))
    if not piano and not bn:
        piano = True
    return piano, bn


def conf(s) -> dict:
    return {"duration": 50.0, "min_gap": 0.17, "supersample": 2, **(s.get("bounce") or {})}


def run_one(s, seed=None, dry_run=False, publish=True, level=None, fmt=None, formats=None, song_id=None, lang=None) -> dict:
    from . import render
    c = conf(s)
    conn = db.connect(config.resolve(s, "database"))
    seed = seed if seed is not None else random.SystemRandom().randrange(1, 1_000_000)
    log.info("▶ Nouvelle vidéo « rebonds » : choix du morceau…")
    control.check()
    tried = set()
    for attempt in range(6):                                          # on écarte les morceaux trop pauvres / trop courts
        sid, midi, meta = pipeline.song_by_id(conn, song_id) if song_id else pipeline.pick_song(conn, s, seed + attempt * 7919, exclude=tried)
        tried.add(sid)
        log.info("♪ Morceau choisi : %s - %s", meta["title"], meta["artist"])
        notes, tempo = parse_midi(midi)
        try:
            notes = arrange_for_piano(notes, parse_midi_info(midi))
        except Exception as e:
            log.warning("arrangement ignoré (%s)", e)
        notes = pipeline.trim_lead(notes)
        if not notes:
            continue
        ana = analyze(notes, tempo)
        sec = select_hook(notes, min(c["duration"], ana["duration"]))
        window = [n for n in notes if n.end > sec["start"] and n.start < sec["end"]]
        onsets = [(t - sec["start"], p) for t, p in choreo.melody_onsets(window, c["min_gap"]) if sec["start"] <= t < sec["end"]]
        if len(onsets) >= 12 and sec["duration"] >= 12:
            break
        log.info("↻ Morceau écarté (trop court ou trop peu de notes) : autre morceau")
    else:
        raise RuntimeError("Plus aucun morceau utilisable pour ce format : ajoute des morceaux plus longs dans Bureau/MIDI")
    log.info("✂ Passage retenu : %.0fs → %.0fs (%d rebonds)", sec["start"], sec["end"], len(onsets))
    if dry_run:
        n0 = conn.execute("SELECT COUNT(*) FROM videos WHERE style LIKE 'bounce|%'").fetchone()[0] + 1
        c0 = _content.generate(meta, n0, seed, set(), lang or s.get("language", "fr"))
        return {"status": "DRY_RUN", "title": c0["title"], "song": meta["title"], "bounces": len(onsets)}
    result = render_for(s, conn, sid, notes, sec, onsets, meta, lang, seed, publish)
    return {**result, "videos": [result]}


def render_for(s, conn, sid, notes, sec, onsets, meta, lang, seed, publish=False) -> dict:
    """Fabrique UNE vidéo « rebonds » à partir de notes et d'un passage déjà choisis (même son que la vidéo de piano du même morceau)."""
    from . import render
    c = conf(s)
    n = conn.execute("SELECT COUNT(*) FROM videos WHERE style LIKE 'bounce|%'").fetchone()[0] + 1
    used = {r[0] for r in conn.execute("SELECT title FROM videos WHERE title IS NOT NULL")}
    content = _content.generate(meta, n, seed, used, lang or s.get("language", "fr"))
    content["format"] = "vertical"
    log.info("✍ [rebonds] Titre : %s", content["title"])
    out_dir = config.resolve(s, "data_dir") / "rendered"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{sid}_{int(time.time())}_bounce.mp4"
    last_err, q, res = "", None, {}
    for attempt in range(3):
        log.info("🎬 [rebonds] Fabrication de la vidéo (tentative %d/3)…", attempt + 1)
        res = {}
        try:
            duration = onsets[-1][0] + 2.4
            render.render_video(notes, onsets, out, content["label"], content["song_artist"], start=sec["start"], duration=duration,
                                result=res, supersample=c["supersample"], seed=seed + attempt)
            q = qc.check(out, 1080, 1920, (10, 75))
            if q["score"] >= s["qc"]["publish_min"]:
                break
            last_err = f"contrôle qualité refusé ({q['score']}/100) : " + ", ".join(q.get("issues") or [])
            log.warning("⚠ %s", last_err)
        except control.Cancelled:
            raise
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            log.error("✖ Rendu échoué : %s", last_err)
            q = None
            Path(out).unlink(missing_ok=True)
    content["banner_px"] = 0
    report = {"song": meta["title"], "section": sec, "difficulty": "bounce", "format": "bounce", "title": content["title"], "engine": "bounce"}
    sec2 = {"duration": round(res.get("duration") or onsets[-1][0] + 2.4, 1), **{k: sec[k] for k in ("start", "end") if k in sec}}
    return _finalize(s, conn, sid, out, sec2, content, report, publish, q, last_err)


def make_pair(s, conn, sid, notes, sec, meta, lang=None, seed=0, publish=False):
    """Vidéo « rebonds » du MÊME morceau que la vidéo de piano : mêmes notes, même passage, donc EXACTEMENT le même son. Retourne le rapport ou None."""
    c = conf(s)
    start, end = sec["start"], sec["end"]
    window = [n for n in notes if n.end > start and n.start < end]
    onsets = [(t - start, p) for t, p in choreo.melody_onsets(window, c["min_gap"]) if start <= t < end]
    if len(onsets) < 12:
        log.info("↷ Vidéo « rebonds » ignorée pour ce morceau (trop peu de notes dans le passage)")
        return None
    try:
        return render_for(s, conn, sid, notes, {"start": start, "end": end}, onsets, meta, lang, seed + 313, publish)
    except control.Cancelled:
        raise
    except Exception as e:
        log.error("✖ Vidéo « rebonds » non faite : %s [%s]", e, __import__("app.director.progress", fromlist=["where"]).where(e))
        return None


def _finalize(s, conn, sid, out, sec, content, report, publish, q, last_err):
    if q is None:
        q = {"score": 0, "issues": [last_err or "rendu échoué"]}
    return pipeline._finalize(s, conn, sid, "bounce", "vertical", VERTICAL, out, sec, content, report, publish, q, last_err)
