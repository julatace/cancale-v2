"""Director : une vidéo de bout en bout, déterministe, avec retry et sans jamais bloquer sur une plateforme."""
import json
import logging
import random
import tempfile
import time
from pathlib import Path

from app import config
from app.content_generator.generate import difficulty_of, generate
from app.database import db
from app.midi_analyzer.analyzer import analyze
from app.midi_analyzer.parser import parse_midi, parse_midi_info
from app.midi_analyzer.arrange import arrange_for_piano
from app.midi_analyzer.fold import choose_lowest, fold_notes
from app.renderer import framing
from app.music_discovery import generator, importer
from app.publisher import adapters
from app.quality_control import qc
from app.section_selector.selector import select_section
from app.section_selector.hook import select_hook
from app.director import control, difficulty
from app.visualizer import falling, synth
from app.synthesia_controller import mac, sync
from app.renderer import compose
from app.renderer.thumbnail import make_thumbnail
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
    mine = [r for r in ok if (r["source"] or "").startswith("user_owned: Fourni")]
    if mine and s.get("songs", {}).get("prefer_mine", True):          # tes morceaux (boîte de réception, ajout manuel) passent d'abord, dans l'ordre d'arrivée
        r = mine[0]
        return r["id"], Path(r["midi_path"]), {"title": r["title"], "artist": r["artist"], "credit": _credit(r["source"])}
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
    """Sous-titre de la vidéo : le compositeur seulement (ni niveau ni BPM à l'écran)."""
    a = (meta.get("artist") or "").strip()
    return "" if a.lower() in ("", "unknown", "inconnu") else a


def _render(s, notes, sec, out, meta, tempo, content=None, F=None) -> str:
    control.check()
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
                cap, crop, recorded = mac.record(td / "s.mid", sec["duration"], td / "cap.mov", cfg, layout=layout)
                if recorded is not None:                                           # arrêté avant la fin : vidéo plus courte
                    usable = recorded - cfg["capture_trim"]
                    if usable < 10:
                        raise RuntimeError("Enregistrement arrêté trop tôt : moins de 10 secondes de vidéo utile.")
                    sec["duration"], sec["stopped_early"] = round(usable, 1), True
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
    res = {}
    falling.render_video(notes, sec["start"], sec["duration"], out, meta["title"], _subtitle(meta, content), fps=30,
                         key_range=(kb["lowest_key"], kb["lowest_key"] + kb["keys"] - 1),
                         layout=falling.HORIZONTAL if F["width"] > F["height"] else falling.VERTICAL, result=res)
    if res.get("duration") and res["duration"] < sec["duration"] - 0.5:
        sec["duration"], sec["stopped_early"] = round(res["duration"], 1), True
    return "builtin"


def _target(F, s, ana) -> float:
    if F.get("duration") == "full":
        return min(F.get("max_duration", 300), ana["duration"])
    return min(s["duration_target"], ana["duration"])


def _formats(s, fmt, formats) -> list[tuple[str, dict]]:
    names = list(formats) if formats else [fmt or s.get("default_format", "vertical")]
    fm = s.get("formats", {})
    return [(n, fm.get(n) or {"width": 1080, "height": 1920, "banner": 300, "shorts": True}) for n in names]


def run_one(s, seed=None, dry_run=False, publish=True, level=None, fmt=None, formats=None, song_id=None, lang=None) -> dict:
    """Une création : UN morceau et UN niveau, rendus dans chaque format demandé (vertical court et/ou horizontal long)."""
    conn = db.connect(config.resolve(s, "database"))
    seed = seed if seed is not None else random.SystemRandom().randrange(1, 1_000_000)
    fmts = _formats(s, fmt, formats)
    log.info("▶ Nouvelle création : recherche d'un morceau libre de droits...")
    done = conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    level_forced = bool(level)
    level, lv = difficulty.choose_level(s, done, level)
    needs_full = any(F.get("duration") == "full" for _, F in fmts)
    log.info("🎯 Niveau : %s (%s BPM) | Formats : %s", lv["label"], lv["bpm"], ", ".join(n for n, _ in fmts))
    control.check()
    tried = set()
    for attempt_song in range(6):                   # on écarte les morceaux trop denses / trop courts pour la demande
        sid, midi, meta = song_by_id(conn, song_id) if song_id else pick_song(conn, s, seed + attempt_song * 7919, exclude=tried)
        tried.add(sid)
        log.info("♪ Morceau choisi : %s - %s", meta["title"], meta["artist"])
        notes, tempo = parse_midi(midi)
        try:
            n_tracks = len({n.track for n in notes})
            notes = arrange_for_piano(notes, parse_midi_info(midi))       # fichier de groupe (karaoké...) -> arrangement de piano
            if n_tracks > 2:
                log.info("🎹 Arrangement de piano : %d pistes -> %d (mélodie, basse, accompagnement), batterie exclue", n_tracks, len({n.track for n in notes}))
        except Exception as e:
            log.warning("arrangement ignoré (%s)", e)
        kb = s["keyboard"]
        kb_lo = choose_lowest(notes, kb["keys"]) if kb.get("adaptive", True) else kb["lowest_key"]
        notes = fold_notes(notes, kb_lo, kb["keys"])                                    # plage jouée, choisie selon le morceau
        base, piece_bpm = notes, analyze(notes, tempo)["bpm"]
        factor = difficulty.speed_factor(piece_bpm, lv["bpm"])
        notes = difficulty.stretch_notes(base, factor)                                  # tempo = niveau
        tempo = [(0.0, lv["bpm"])]
        ana = analyze(notes, tempo)
        log.info("🔎 Analyse : %s notes, durée %ss (tempo x%.2f -> %s BPM)", ana["note_count"], ana["duration"], factor, lv["bpm"])
        first_sec = select_section(notes, _target(fmts[0][1], s, ana))
        min_len = max(F.get("min_duration", 0) for _, F in fmts)         # chaque vidéo doit durer au moins 1 minute
        too_short = ana["duration"] < min_len
        if not song_id and not level_forced and not too_short and first_sec["density"] > lv["max_density"]:
            dcfg = difficulty.config(s)                   # niveau non imposé : on essaie un niveau plus rapide plutôt que de jeter ton morceau
            for name2, lv2 in sorted(dcfg["levels"].items(), key=lambda kv: kv[1]["bpm"]):
                if lv2["bpm"] <= lv["bpm"] or name2 not in dcfg["rotation"]:
                    continue
                n2 = difficulty.stretch_notes(base, difficulty.speed_factor(piece_bpm, lv2["bpm"]))
                a2 = analyze(n2, [(0.0, lv2["bpm"])])
                f2 = select_section(n2, _target(fmts[0][1], s, a2))
                if f2["density"] <= lv2["max_density"] and a2["duration"] >= min_len:
                    log.info("↗ Niveau %s -> %s : le morceau est trop dense pour %s", lv["label"], lv2["label"], lv["label"])
                    level, lv, notes, tempo, ana, first_sec = name2, lv2, n2, [(0.0, lv2["bpm"])], a2, f2
                    break
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
    reports, plans = [], []
    for k, (fmt_name, F) in enumerate(fmts):
        sec = select_section(notes, _target(F, s, ana)) if F.get("duration") == "full" else select_hook(notes, _target(F, s, ana))
        log.info("✂ [%s] Passage retenu : %ss → %ss (%s)", fmt_name, sec["start"], sec["end"], sec["reason"])
        content = generate(song, diff, seed + k, used, lv["bpm"], lang or s.get("language", "fr"))
        content["format"], content["shorts"] = fmt_name, bool(F.get("shorts", True))
        content["song_title"], content["song_artist"] = meta["title"], _subtitle(meta, content)
        used.add(content["title"])
        if meta.get("credit"):
            content["description"] += f"\n\nMIDI : {meta['credit']}"
        log.info("✍ [%s] Titre : %s", fmt_name, content["title"])
        report = {"song": meta["title"], "section": sec, "difficulty": diff, "bpm": lv["bpm"], "format": fmt_name, "title": content["title"]}
        if dry_run:
            reports.append({**report, "status": "DRY_RUN"})
            break
        plans.append((fmt_name, F, sec, content, report))
    _cover_hook(plans, ana["duration"])
    if plans and not dry_run:
        reports = _make_videos(s, conn, sid, level, plans, notes, tempo, meta, lv, publish, kb_lo)
    if len(reports) == 1:
        return reports[0]
    ok = [r["status"] in ("READY", "PUBLISHED") for r in reports]
    return {"song": meta["title"], "difficulty": diff, "bpm": lv["bpm"], "videos": reports,
            "status": "READY" if all(ok) else "PARTIAL" if any(ok) else "FAILED"}


def _failed(s, conn, sid, level, plans, err) -> list[dict]:
    log.error("✖ ÉCHEC : %s", err)
    out = []
    for fmt_name, F, sec, content, report in plans:
        db.log_error(conn, "render", err)
        path = config.resolve(s, "data_dir") / "rendered" / f"{sid}_{int(time.time())}_{fmt_name}.mp4"
        out.append(_finalize(s, conn, sid, level, fmt_name, F, path, sec, content, report, False, None, err))
    return out


def _cover_hook(plans, total: float):
    """Si une vidéo longue ET une courte sont demandées : l'enregistrement de la longue doit contenir le refrain de la courte."""
    shorts = [p for p in plans if p[1].get("duration") != "full"]
    longs = [p for p in plans if p[1].get("duration") == "full"]
    if not shorts or not longs:
        return
    hook, sec = shorts[0][2], longs[0][2]
    if hook["start"] >= sec["start"] - 1e-6 and hook["end"] <= sec["end"] + 1e-6:
        return
    start = min(max(hook["start"] - (sec["duration"] - hook["duration"]) / 2, 0.0), max(total - sec["duration"], 0.0))
    sec["start"], sec["end"] = round(start, 1), round(start + sec["duration"], 1)


def _make_videos(s, conn, sid, level, plans, notes, tempo, meta, lv, publish, kb_lo=None) -> list[dict]:
    """Synthesia : UN SEUL enregistrement dont on tire tous les formats. Sinon (ou en secours) rendu intégré, format par format."""
    cfg = s.get("synthesia", {})
    mode = s.get("engine", "auto")
    ready = mode != "builtin" and mac.ready(cfg)
    if mode == "synthesia" and not ready:
        return _failed(s, conn, sid, level, plans, "RuntimeError: engine=synthesia mais le Mac n'est pas prêt")
    if ready:
        try:
            return _synthesia_batch(s, conn, sid, level, plans, notes, meta, lv, publish, kb_lo)
        except control.Cancelled:
            raise
        except Exception as e:
            if mode == "synthesia":                             # forcé : on montre l'erreur, pas de repli discret
                return _failed(s, conn, sid, level, plans, f"{type(e).__name__}: {e}")
            log.error("Synthesia a échoué (%s) -> rendu intégré", e)
    s_builtin = {**s, "engine": "builtin"}
    if kb_lo is not None:
        s_builtin["keyboard"] = {**s["keyboard"], "lowest_key": kb_lo}
    return [_produce(s_builtin, conn, sid, level, fmt_name, F, notes, tempo, sec, meta, content, report, publish)
            for fmt_name, F, sec, content, report in plans]


def _synthesia_batch(s, conn, sid, level, plans, notes, meta, lv, publish, kb_lo=None) -> list[dict]:
    cfg = s["synthesia"]
    kb = s["keyboard"]
    kb_lo = kb["lowest_key"] if kb_lo is None else kb_lo
    maximized = cfg.get("window_mode", "maximized") == "maximized"
    out_dir = config.resolve(s, "data_dir") / "rendered"
    out_dir.mkdir(parents=True, exist_ok=True)
    full_plans = [p for p in plans if p[1].get("duration") == "full"]
    R = dict((full_plans[0] if full_plans else plans[0])[2])            # l'enregistrement couvre le format le plus long
    reports = []
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        log.info("🎥 Un seul enregistrement de %.0f s pour %d format(s)", R["duration"], len(plans))
        (td / "s.mid").write_bytes(trim_midi(notes, R["start"], R["start"] + R["duration"], bpm=lv["bpm"]))
        cap, crop, recorded = mac.record(td / "s.mid", R["duration"], td / "cap.mov", cfg, layout=(1080, 1920, 300))
        avail = None                                                   # durée de vidéo utilisable si arrêt anticipé
        if recorded is not None:
            avail = recorded - cfg["capture_trim"]
            if avail < 10:
                raise RuntimeError("Enregistrement arrêté trop tôt : moins de 10 secondes de vidéo utile.")
        mac.debug_frames(cap, config.resolve(s, "data_dir") / "debug")
        inside = [n for n in notes if n.end > R["start"] and n.start < R["start"] + R["duration"]]
        first = max(min(n.start for n in inside) - R["start"], 0.0)
        t_on = sync.detect_first_note(cap, crop, cfg["capture_trim"])
        if t_on is None:
            t_on = cfg.get("first_note_seconds", 2.5)
            log.warning("calage auto impossible -> repli sur %.1fs", t_on)
        else:
            log.info("🎚 Calage du son : 1re note visible à %.1fs dans la vidéo", t_on)
        try:
            screen_pts = mac.screen_points()
        except Exception:
            screen_pts = (1470, 956)
        content_crop = crop or (0.0, 0.0, 1.0, 1.0)
        bg = compose.sample_bg_color(cap, content_crop, cfg["capture_trim"] + 1.0)      # gris du fond de Synthesia
        log.info("🎨 Couleur de fond mesurée : RGB%s", bg)
        played = framing.measure_played_range(cap, cfg["capture_trim"], content_crop, margin=kb.get("margin_ratio", 0.22)) if maximized else None
        if played is not None:
            log.info("📐 Zone jouée mesurée : de %.0f %% à %.0f %% de la largeur de la fenêtre (marge incluse)", played[0] * 100, played[1] * 100)
        else:
            log.warning("📐 Zone jouée non mesurable : cadrage estimé d'après le clavier supposé")
        mac.debug_crop(cap, cfg["capture_trim"] + 10, framing.crop_from_range(content_crop, screen_pts, *played, 1080 / 1620) if played else content_crop,
                       config.resolve(s, "data_dir") / "debug")
        for fmt_name, F, sec, content, report in plans:
            control.check()
            full = F.get("duration") == "full"
            v0, dur = 0.0, min(R["duration"], avail) if avail else R["duration"]
            if not full:                                               # extrait vertical : le refrain, DANS l'enregistrement
                v0 = sec["start"] - R["start"]
                dur = sec["duration"]
                if v0 < -1e-6 or v0 + dur > R["duration"] + 0.5:       # hors enregistrement : refrain recherché à l'intérieur
                    inner = [type(n)(n.start - R["start"], n.end - R["start"], n.pitch, n.velocity, n.track) for n in inside]
                    sub = select_hook(inner, min(s["duration_target"], R["duration"] if avail is None else min(R["duration"], avail)))
                    v0, dur = sub["start"], sub["duration"]
                v0 = max(v0, 0.0)
            d = t_on + v0 - first                                      # instant vidéo où commence l'extrait
            trim = cfg["capture_trim"] + max(d, 0.0)
            shift = t_on - first - max(d, 0.0)
            if avail is not None:
                dur = min(dur, avail - max(d, 0.0))
            sec = {**sec, "start": R["start"] + v0, "end": R["start"] + v0 + dur, "duration": round(dur, 1),
                   **({"stopped_early": True} if avail is not None and dur < sec["duration"] - 0.5 else {})}
            clip = [type(n)(n.start - R["start"] + shift, n.end - R["start"] + shift, n.pitch, n.velocity, n.track) for n in inside]
            wav = td / f"a_{fmt_name}.wav"
            synth.write_wav(wav, synth.render_audio([type(n)(n.start - v0, n.end - v0, n.pitch, n.velocity, n.track) for n in clip], 0, dur))
            out = out_dir / f"{sid}_{int(time.time())}_{fmt_name}.mp4"
            log.info("🎬 [%s] Montage depuis l'enregistrement (%.0f s)", fmt_name, dur)
            sub_txt = _subtitle(meta, content)
            wide = F["width"] > F["height"]
            if wide and not maximized:                                 # fenêtre verticale : app au centre, titre sur les côtés
                compose.compose_landscape(cap, wav, out, trim, dur, meta["title"], sub_txt, "", content.get("hook", ""), content.get("cta", ""), crop=crop, bg=bg)
            else:
                use = content_crop
                if maximized and not wide:                             # zoom sur la zone où les notes tombent réellement
                    aspect = F["width"] / (F["height"] - F["banner"] - compose.bottom_for(F["width"], F["height"]))
                    if played is not None:
                        use = framing.crop_from_range(content_crop, screen_pts, played[0], played[1], aspect)
                    else:                                              # mesure impossible : estimation d'après le clavier supposé
                        use = framing.vertical_crop(content_crop, screen_pts, kb_lo, kb_lo + kb["keys"] - 1,
                                                    kb.get("display_lowest", 21), kb.get("display_keys", 88), aspect, kb.get("margin_keys", 6))
                compose.compose_vertical(cap, wav, out, trim, dur, meta["title"], subtitle=sub_txt, hook=content.get("hook", ""),
                                         cta=content.get("cta", ""), crop=use if (maximized or not wide) else crop,
                                         size=(F["width"], F["height"]), top=F["banner"], bg=bg)
            report["engine"] = "synthesia"
            _w, _h, _y = compose.app_box(compose._probe_size(cap), use if not (wide and not maximized) else None, F["width"], F["height"], F["banner"])
            content["banner_px"] = max(int(_y), F["banner"]) if not (wide and not maximized) else 0
            log.info("✔ Contrôle qualité...")
            low = 5 if sec.get("stopped_early") else (min(30, F.get("max_duration", 300) * 0.5) if full else 3)
            hi = (F.get("max_duration", 300) + 10) if full else (s["duration_range"][1] + 5)
            result = qc.check(out, expect_w=F["width"], expect_h=F["height"], dur_range=(low, hi))
            report["section"] = sec
            reports.append(_finalize(s, conn, sid, level, fmt_name, F, out, sec, content, report, publish, result))
    return reports


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
            if sec.get("stopped_early"):
                dur_range = (5, dur_range[1])                      # vidéo volontairement raccourcie
            result = qc.check(out, expect_w=F["width"], expect_h=F["height"], dur_range=dur_range)
            if qc.verdict(result["score"], publish_min=s["qc"]["publish_min"], autofix_min=s["qc"]["autofix_min"]) == "PUBLISH":
                break
            log.warning("QC %s (tentative %d): %s", result["score"], attempt, result["issues"])
        except control.Cancelled:
            raise                                       # arrêt demandé : pas de nouvelle tentative
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            db.log_error(conn, "render", last_err, retry_count=attempt)
            log.error("rendu échoué (tentative %d): %s", attempt, e)
            if s.get("engine") == "synthesia":
                break                                   # mode forcé : une seule tentative, on veut l'erreur
    return _finalize(s, conn, sid, level, fmt_name, F, out, sec, content, report, publish, result, last_err)


def _finalize(s, conn, sid, level, fmt_name, F, out, sec, content, report, publish, result, last_err="") -> dict:
    """Contrôle qualité déjà fait : enregistre la vidéo en base et publie."""
    ok = result is not None and result["score"] >= s["qc"]["publish_min"]
    log.info("✔ [%s] Score qualité : %s/100 -> %s", fmt_name, result["score"] if result else 0, "OK" if ok else "REFUSÉE")
    if ok:                                                      # miniature : image de la vidéo + titre du morceau
        try:
            banner = content.get("banner_px")
            if banner is None:                                  # rendu intégré : hauteur du bandeau selon le format
                banner = falling.HORIZONTAL.TOP if F["width"] > F["height"] else falling.VERTICAL.TOP
            th = make_thumbnail(out, Path(out).with_suffix(".jpg"), content.get("song_title") or content["title"], content.get("song_artist", ""),
                                top_crop=int(banner))
            content["thumbnail"] = str(th)
            log.info("🖼 [%s] Miniature créée : %s", fmt_name, th.name)
        except Exception as e:
            log.warning("miniature non créée (%s)", e)
    post = {k: content.get(k) for k in ("title", "description", "tiktok_caption", "instagram_caption", "youtube_title", "pinned_comment", "hashtags")}
    post["thumbnail"] = Path(content["thumbnail"]).name if content.get("thumbnail") else None
    vid = conn.execute("INSERT INTO videos(song_id,style,duration,output_path,quality_score,status,title,meta,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                       (sid, f"{level}|{fmt_name}", sec["duration"], str(out), result["score"] if result else 0,
                        "READY" if ok else "FAILED", content["title"], json.dumps(post, ensure_ascii=False), db.now())).lastrowid
    report["post"] = post
    conn.commit()
    report.update(video_id=vid, video=str(out), qc=result, status="READY" if ok else "FAILED", publications=[])
    if last_err and not ok:
        report["error"] = last_err
        log.error("✖ ÉCHEC : %s", last_err)
    if ok and publish:
        for ad in adapters(s, fmt=fmt_name):
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
