# Le procédé complet, de A à Z (piano : de la création à la publication)

Ce document explique TOUT, étape par étape, avec les fichiers et les fonctions concernés. Le code complet est dans `piano_code_complet.zip` (même contenu que le dépôt `julatace/cancale-v2`, dossier `piano-studio-ai/`). Lis d'abord `HANDOFF.md` (règles de l'utilisateur) puis ce fichier.

## Vue d'ensemble

```
Bureau/MIDI ──► inbox.scan ──► base songs ──► pick_song ──► parse_midi/arrange/fold ──► _fit_tempo (niveau, vitesse)
      ──► select_hook/select_section (passage) ──► generate (titre, texte, hashtags)
      ──► sketch.render_video (images + son + contrôle) ──► QC + miniature ──► table videos (READY)
      ──► agenda / pilote automatique (créneaux futurs) ──► publish_video : TikTok puis YouTube (programmé DANS les réseaux)
      ──► suppression du Mac + notification
```
Tout est orchestré par `app/ui/server.py` (`Job._produce`) ; une seule vidéo est fabriquée puis envoyée à la fois ; l'agenda décide des dates ; les réseaux publient eux-mêmes à l'heure.

## Étape 1 — Les morceaux (fichiers MIDI de l'utilisateur)
- Dossier surveillé : `~/Desktop/MIDI` (`inbox.watch` dans `config/settings.yaml`). Boucle `due_runner` (`app/ui/server.py`) toutes les 30 s.
- `app/music_discovery/inbox.py` : `waiting`, `watched_pending`, `scan(s, import_upload)`. Rien n'est importé tant que la case « droits » n'est pas cochée (`rights_confirmed`). Les fichiers d'origine ne sont ni déplacés ni modifiés.
- `app/music_discovery/importer.py` : crée la ligne `songs` (`license='LEGAL_CONFIRMED'`, `source LIKE 'user_owned: Fourni%'`).
- Règle de sécurité (CLAUDE.md) : seul un morceau `LEGAL_CONFIRMED` entre dans le pipeline (`database.db.song_usable`, délai de réutilisation `same_song_cooldown_days: 30`).

## Étape 2 — Choix du morceau (`pick_song`, `app/director/pipeline.py`)
Réglage `songs.only_mine: true` : uniquement les morceaux de l'utilisateur, les nouveaux d'abord ; pas deux fois le même artiste d'affilée ; un morceau utilisé récemment est écarté. Si un morceau est trop dense / trop court pour le niveau, l'agent en essaie un autre (jusqu'à 6 fois) ou monte d'un niveau.

## Étape 3 — Lecture et arrangement
```python

notes, tempo = parse_midi(midi)
        try:
            n_tracks = len({n.track for n in notes})
            notes = arrange_for_piano(notes, parse_midi_info(midi))       # fichier de groupe (karaoké...) -> arrangement de piano
            if n_tracks > 2:
                log.info("🎹 Arrangement de piano : %d pistes -> %d (mélodie, basse, accompagnement), batterie exclue", n_tracks, len({n.track for n in notes}))
        except Exception as e:
            log.warning("arrangement ignoré (%s)", e)
        kb = s0["keyboard"]
        if kb.get("adaptive", True):                                         # étendue réelle du morceau (octaves entières), sans écraser les notes rares
            kb_lo, kb_n = choose_span(notes, kb["keys"], kb.get("max_keys", 60))
        else:
            kb_lo, kb_n = kb["lowest_key"], kb["keys"]
        notes = fold_notes(notes, kb_lo, kb_n)
        s = {**s0, "keyboard": {**kb, "keys": kb_n}}                          # la suite (cadrage, rendu) utilise cette étendue
        log.info("🎹 Touches : %d touches à partir de la note %d", kb_n, kb_lo)
```
- `app/midi_analyzer/parser.py` (`parse_midi`, `Note(start,end,pitch,velocity,track,channel)`), `arrange.py` (fichier de groupe/karaoké → 3 pistes de piano, batterie exclue), `fold.py` (`choose_span` : étendue réelle en octaves entières ; `fold_notes` : replie les notes hors clavier).

## Étape 4 — Niveau et tempo (`app/director/difficulty.py`, `_fit_tempo`)
Niveau = tempo cible : Facile 80 / Moyen 100 / Difficile 130 BPM (`difficulty.levels` dans les réglages). `stretch_notes(notes, factor)` étire les temps pour atteindre ce tempo ; `comfortable_extra` ralentit encore (jusqu'à ×0,5) si des passages sont trop rapides à lire. Un niveau trop facile pour un morceau dense est relevé plutôt que le morceau écarté.
```python

def _fit_tempo(base, piece_bpm: float, lv: dict):
    """Étire le morceau au tempo du niveau, puis le ralentit encore si le passage le plus rapide dépasse la vitesse lisible du niveau.
    Retourne (notes, niveau avec son tempo réel, table de tempo, facteur total, ralentissement supplémentaire)."""
    factor = difficulty.speed_factor(piece_bpm, lv["bpm"])
    notes = difficulty.stretch_notes(base, factor)
    extra = difficulty.comfortable_extra(notes, lv.get("max_rate"))
    if extra < 1.0:
        notes = difficulty.stretch_notes(notes, extra)
    lv2 = {**lv, "bpm": round(lv["bpm"] * extra, 1)}
    return notes, lv2, [(0.0, lv2["bpm"])], factor * extra, extra


```

## Étape 5 — Le passage (≈ 1 minute en vertical, morceau entier en horizontal)
`app/section_selector/hook.py::select_hook` (refrain repéré : thème qui revient le plus) pour le vertical ; `selector.py::select_section` pour l'horizontal. Le passage est un `{start, end, duration, reason}`.

## Étape 6 — Titre, description, hashtags (`app/content_generator/generate.py`)
`generate(song, difficulty, seed, used_titles, bpm, lang)` : titre « Morceau - accroche » (l'accroche est choisie parmi celles PAS déjà utilisées dans les titres précédents), description (accroche, morceau, niveau, appel à l'action, hashtags), `tiktok_caption`, `youtube_title`, `hashtags` (#pianocover #pianotutorial #easypiano #piano + #morceau + #compositeur, 6 max). `pipeline.clean_artist` retire toute mention de licence (« (public domain) »).

## Étape 7 — Fabrication de la vidéo (`app/visualizer/sketch.py`, style dessiné)
`pipeline._render` appelle `sketch.render_video(notes, start, duration, out, title, subtitle, layout, view, supersample, hook, cta)`. Repli automatique sur l'ancien rendu intégré si le style dessiné échoue. Synthesia n'est plus nécessaire (`style: sketch` par défaut).
1. `clean_notes` : hauteurs valides (21–108), doublons supprimés, même touche rejouée = petit creux visible, durée minimale.
2. `Camera` : caméra FIXE si tout le morceau tient (jusqu'à 52 touches blanches) ; sinon glissement lent plafonné (5 touches/s) ; vue `wide` par défaut.
3. `render_frame` (Pillow, en double taille puis `reduce(2)`) : fond papier à grain, barres colorées au trait (turquoise main gauche < point de partage, orange main droite ; `hand_split_for` suit le morceau), noms de notes, prochaine note en relief, lueur d'impact, clavier crayonné ; le bas de la barre touche le clavier EXACTEMENT au début de la note ; notes visibles 3,6 s à l'avance.
4. `_title` : titre sur 2 lignes sans débordement, compositeur, accroche (2,6 premières secondes), appel à l'action (3 dernières secondes) ; fondu d'entrée/sortie.
5. Son : `synth.render_audio` = piano macOS via `afconvert` (GM + pédale auto + légère réverbération) ou piano numpy de secours ; `align_audio` mesure le décalage son/notes (`onset_lag`) et recale si > 12 ms.
6. Encodage ffmpeg (images brutes → H.264 CRF 16 preset fast, AAC 256 kbps, `loudnorm=I=-14:TP=-1.5`). Écrit sous `nom.part.mp4` puis renommé ; garde-fou si ffmpeg se bloque.
7. Contrôles : `verify_video` (lisible, image + son, durée), `measure_sync` (décalage mesuré sur le fichier final, journal si > 40 ms).
```python

def render_frame(notes, t, cam_range, L: Layout, split=60, pressed=None):
    W, H, TOP, KB_H = L.W, L.H, L.TOP, L.KB_H
    a, b = cam_range
    sx = W / (b - a)
    img = _paper(W, H).copy()
    d = ImageDraw.Draw(img)
    fall_bot = H - KB_H
    lw = max(int(sx * 0.09), 4)
    for o in range(0, 11):                                                    # pointillés à chaque Do
        x = (o * 7 - a) * sx
        if 0 <= x <= W:
            for y in range(TOP, int(fall_bot), 36):
                d.line([(x, y), (x, y + 18)], fill=(190, 186, 180), width=3)
    visible = sorted((n for n in notes if n.end >= t and n.start <= t + LOOKAHEAD), key=lambda n: n.start)
    for i, n in enumerate(visible):
        px, pw, blk = xpos(n.pitch)
        x0, x1 = (px - a) * sx + sx * 0.04, (px + pw - a) * sx - sx * 0.04
        if x1 < 0 or x0 > W:
            continue
        y1 = fall_bot - (n.start - t) / LOOKAHEAD * (fall_bot - TOP)             # le bas de la barre touche le clavier EXACTEMENT au début de la note
        y0 = fall_bot - (n.end - t) / LOOKAHEAD * (fall_bot - TOP)
        y0, y1 = max(y0, TOP), min(y1, fall_bot)
        if y1 - y0 < 6:
            continue
        col = LEFT if n.pitch < split else RIGHT
```

## Étape 8 — Qualité et miniature
`app/quality_control/qc.py::check` (score /100 : résolution, audio présent, durée, écran noir, image figée, volume trop faible ; publication si ≥ 90, sinon nouvel essai/autre morceau). `app/renderer/thumbnail.py` : miniature (titre en gros, compositeur) sauvegardée à côté de la vidéo. La ligne `videos` passe en `READY` (`_finalize`).

## Étape 9 — Quand publier : agenda et pilote automatique
- Agenda (page) : nombre de vidéos par jour sur ≤ 10 jours → `squeue.slots_for_days(days, times)` donne des créneaux TOUJOURS dans le futur (≥ 30 min), heures `12:30, 19:00` puis `09:00, 11:00, 16:00, 21:00` ; le surplus d'un jour passé passe au suivant.
- Pilote automatique (`app/scheduler/autopilot.py`) : `deficit` compte ce qui est déjà programmé (traces `schedule.status='DONE'` à venir) et calcule ce qui manque ; `AutoPilot.decide` lance UNE fabrication ; pause progressive 30 min → 6 h après un échec.
```python

def deficit(s, conn, now: datetime | None = None) -> list[dict]:
    """[{"date": "2026-10-12", "count": 1}, ...] : ce qu'il manque pour atteindre per_day sur la fenêtre, créneaux réellement disponibles seulement."""
    c = conf(s)
    now = now or datetime.now(timezone.utc)
    have = scheduled_by_day(conn, now)
    out = []
    for i in range(c["days"]):
        day = (now.astimezone() + timedelta(days=i)).date().isoformat()
        miss = c["per_day"] - have.get(day, 0)
        if miss <= 0:
            continue
        slots = [x for x in squeue.slots_for_days([{"date": day, "count": miss}], c["times"], now.astimezone()) if x.date().isoformat() == day]
        if slots:                                                  # aujourd'hui : plus d'heure libre = on n'y revient pas
            out.append({"date": day, "count": len(slots)})
    return out


```
- `Job._produce` (`app/ui/server.py`) : pour chaque créneau : `RUNNER` (fabrication) → `publish_video(..., publish_at=slot)` DÈS le montage → suivante. Jusqu'à `count + min(count,4)` essais ; seule la dernière fabrication est envoyable (`last_batch.json`).

## Étape 10 — Publication (`app/scheduler/queue.py::publish_video`)
Détail navigateur dans `COMMENT_JE_PUBLIE.md`. Résumé du code :
```python

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
    if not _proc_lock_acquire():
        SEND_LOCK.release()
        return [{"platform": "app", "status": "FAILED", "detail": "un autre agent utilise Chrome depuis trop longtemps : rien n'a été renvoyé"}]
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
            if ad.platform == "youtube" and youtube_capacity(s, conn) <= 0:               # limite quotidienne de YouTube atteinte : on garde la vidéo, TikTok part quand même
                free = youtube_free_at(s, conn)
                conn.execute("INSERT OR REPLACE INTO publications(video_id,platform,post_id,status,published_at) VALUES(?,?,?,?,?)",
                             (video_id, "youtube", (when.replace(tzinfo=None).isoformat(timespec="minutes") if when else ""), "WAITING", db.now()))
                conn.commit()
                out.append({"platform": "youtube", "status": "WAITING",
                            "detail": f"limite de {s.get('youtube', {}).get('max_uploads_per_day', 4)} envois par 24 h atteinte : reprise automatique vers {free:%d/%m %H:%M} (page ouverte)"})
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

```
- `native_time(publish_at)` : l'heure doit être ≥ 20 min et ≤ 10 jours dans le futur, sinon la vidéo n'est PAS envoyée.
- `adapters(s2, fmt=fmt)` (`app/publisher/__init__.py`) : TikTok (`tiktok_web.TikTokWeb`) puis YouTube (`youtube_web.YouTubeWeb`) ; la vidéo horizontale ne va qu'à YouTube.
- Verrous : `SEND_LOCK` (processus) + `_proc_lock_acquire` (`data/.send.lock`, entre agents).

## Étape 11 — Après l'envoi
`cleanup.delete_after_publish` supprime vidéo, miniature et copie de secours quand TOUTES les plateformes sont bonnes (PUBLISHED / SCHEDULED / DRAFT). `notify.send` : notification macOS (lot programmé, envois à vérifier, plus de morceaux). Au démarrage : `purge_partial`, `purge_published`, `purge_orphans`. Bilan 24 h dans la page (`/api/health`).

## Lancer, tester, déboguer
- `./p.sh ui` (page http://127.0.0.1:8765), `./p.sh autostart`, `./p.sh shortcuts` (boutons Bureau), `./p.sh post FICHIER --at "AAAA-MM-JJ HH:MM"`.
- Réglages : `config/settings.yaml` + `data/local_settings.json`. Autre agent : `PIANO_INSTANCE=nom`.
- Tests : `python -m pytest -q` (~250 tests). Test de bout en bout sans publier : `pipeline.run_one(s, publish=False, formats=["vertical","horizontal"])`.
- Journal en direct : page → « Détails techniques ». Captures des étapes de publication : `data/debug/steps/`.

## Fichiers clés (tout est dans le zip)
`app/director/pipeline.py`, `app/director/difficulty.py`, `app/visualizer/sketch.py`, `app/visualizer/synth.py`, `app/content_generator/generate.py`, `app/scheduler/queue.py`, `app/scheduler/autopilot.py`, `app/publisher/tiktok_web.py`, `app/publisher/youtube_web.py`, `app/ui/server.py`, `app/ui/page.py`, `app/director/cleanup.py`, `app/clips/__init__.py`, `config/settings.yaml`, `p.sh`.
