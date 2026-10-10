import argparse
import sys
from pathlib import Path

from . import config, doctor
from .database import db
from .logging_setup import setup_logging


def cmd_doctor(s, a):
    text, ready = doctor.render(doctor.run_checks(s, config.ROOT), doctor.internet_ok())
    print(text)
    return 0 if ready else 1


def cmd_status(s, a):
    conn = db.connect(config.resolve(s, "database"))
    n = lambda q: conn.execute(q).fetchone()[0]
    print(f"Mode: {s['mode']} | {s['videos_per_day']} vidéos/jour")
    legal = n("SELECT COUNT(*) FROM songs WHERE license='LEGAL_CONFIRMED'")
    print(f"Morceaux: {n('SELECT COUNT(*) FROM songs')} (légaux: {legal})")
    print(f"Vidéos: {n('SELECT COUNT(*) FROM videos')} | Publications: {n('SELECT COUNT(*) FROM publications')}")
    print(f"Erreurs: {n('SELECT COUNT(*) FROM errors')}")
    return 0


def cmd_queue(s, a):
    conn = db.connect(config.resolve(s, "database"))
    rows = conn.execute("SELECT status, COUNT(*) c FROM videos GROUP BY status").fetchall()
    for r in rows or []:
        print(f"{r['status']}: {r['c']}")
    if not rows:
        print("File vide")
    return 0


def cmd_init(s, a):
    db.connect(config.resolve(s, "database"))
    print("Base initialisée.")
    return 0


def cmd_import(s, a):
    from .music_discovery import importer
    conn = db.connect(config.resolve(s, "database"))
    r = importer.import_midi(conn, a.file, a.title, a.artist, a.source, a.license_proof,
                             dest_dir=config.resolve(s, "data_dir") / "midi", allowed=set(s["allowed_sources"]))
    print(f"{r['status']}: {r['reason']}")
    return 0 if r["status"] == "LEGAL_CONFIRMED" else 1


def cmd_analyze(s, a):
    import json
    from .midi_analyzer.analyzer import analyze
    from .midi_analyzer.parser import parse_midi
    from .section_selector.selector import select_section
    notes, tempo = parse_midi(a.file)
    print(json.dumps({"analysis": analyze(notes, tempo),
                      "section": select_section(notes, a.duration or s["duration_target"])}, indent=2, ensure_ascii=False))
    return 0


def cmd_run(s, a):
    import json
    from .director.pipeline import run_one
    code = 0
    if getattr(a, "force_synthesia", False):  # test d'étalonnage : force Synthesia, sans publier
        s["synthesia"]["calibrated"] = True
        s["engine"] = "synthesia"
    for _ in range(a.count):
        r = run_one(s, dry_run=a.dry_run, publish=not getattr(a, 'force_synthesia', False))
        print(json.dumps(r, indent=2, ensure_ascii=False, default=str))
        code |= r["status"] not in ("PUBLISHED", "READY", "DRY_RUN")
    return code


def cmd_mac_check(s, a):
    from .synthesia_controller import mac
    ok_all = True
    for name, ok, detail in mac.check(s["synthesia"]):
        print(f"{'✅' if ok else '❌'} {name}  {detail}")
        ok_all &= ok
    print("\nPrêt : le mode Synthesia sera utilisé." if ok_all else "\nPas prêt : le rendu intégré sera utilisé en repli.")
    return 0 if ok_all else 1


def cmd_mac_test(s, a):
    """Test rapide (~15 s) : ouvre un MIDI, clique « Continuer », photographie l'écran avant/après."""
    import time
    from .music_discovery import generator
    from .synthesia_controller import mac
    cfg = s["synthesia"]
    dbg = config.resolve(s, "data_dir") / "debug"
    dbg.mkdir(parents=True, exist_ok=True)
    midi = dbg / "test.mid"
    midi.write_bytes(generator.compose(1)[0])
    mac.osa('tell application "Synthesia" to quit'); time.sleep(2)
    mac.sh(["open", "-a", cfg["app_path"], str(midi)]); time.sleep(cfg["load_seconds"])
    print("Fenêtre Synthesia (x, y, largeur, hauteur) :", mac.window_geometry())
    mac.sh(["screencapture", "-x", str(dbg / "1_avant_clic.png")])
    print("Action :", mac.start_playback(cfg))
    time.sleep(6)
    mac.sh(["screencapture", "-x", str(dbg / "2_apres_clic.png")])
    print(f"Photos : {dbg}/1_avant_clic.png et 2_apres_clic.png  (ouvrir : open {dbg})")
    return 0


def cmd_fetch_midi(s, a):
    """Test de la recherche en ligne : affiche ce qui est trouvé, importe si la licence est valide."""
    import random
    from .music_discovery import importer, mutopia
    conn = db.connect(config.resolve(s, "database"))
    res = mutopia.fetch_one(rnd=random.Random(), debug=print)
    if not res:
        print("Rien de valide trouvé (site inaccessible ou HTML différent de celui attendu)."); return 1
    info, data = res
    f = config.resolve(s, "data_dir") / "midi" / "fetched.mid"
    f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(data)
    r = importer.import_midi(conn, f, info["title"], info["composer"], "public_domain", f"Mutopia {info['license']} {info['page']}", dest_dir=f.parent)
    print(info["title"], "|", info["composer"], "|", info["license"], "->", r["status"])
    return 0


def cmd_mac_rec_test(s, a):
    from .synthesia_controller import mac
    dbg = config.resolve(s, "data_dir") / "debug"
    dbg.mkdir(parents=True, exist_ok=True)
    try:
        backend, enc = mac.pick_backend(s["synthesia"], probe=dbg / "rec_test.mov")
        print(f"✅ Enregistrement d'écran : OK avec {backend}{' (' + enc + ')' if enc else ''}")
        return 0
    except RuntimeError as e:
        print(f"❌ {e}")
        return 1


def cmd_mac_setup(s, a):
    """Prépare le Mac : ouvre directement les réglages d'autorisation, déclenche la demande macOS, vérifie."""
    import time
    from .synthesia_controller import mac
    print("1/3 Ouverture de Réglages > Enregistrement de l'écran : cochez Terminal (et quittez/relancez le Terminal si demandé).")
    mac.sh(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"])
    time.sleep(1)
    mac.sh(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"])
    print("2/3 Test de l'enregistrement d'écran (macOS peut afficher « Autoriser » : cliquez dessus)...")
    dbg = config.resolve(s, "data_dir") / "debug"
    dbg.mkdir(parents=True, exist_ok=True)
    ok, msg = mac.rec_test(dbg / "rec_test.mp4", seconds=3)
    print(("✅ " if ok else "❌ ") + msg)
    print("3/3 Diagnostic complet :")
    return cmd_mac_check(s, a) if ok else 1


def cmd_ui(s, a):
    from .ui import server
    server.serve(port=a.port or int((s.get("ui") or {}).get("port", 8765)), open_browser=not a.no_browser)
    return 0


def cmd_post(s, a):
    """Poste UNE vidéo sur TikTok puis YouTube, programmée dans leurs plannings si --at est donné (sinon publication immédiate seulement avec --now)."""
    from datetime import datetime
    from . import clips
    from .scheduler import queue as squeue
    when = None
    if a.at:
        try:
            when = datetime.fromisoformat(a.at.replace("T", " ")).astimezone()
        except ValueError:
            print("❌ Date invalide. Exemple : --at \"2026-10-12 19:00\"")
            return 1
    elif not a.now:
        print("❌ Indique QUAND : --at \"2026-10-12 19:00\" (programmé dans TikTok et YouTube) ou --now (tout de suite).")
        return 1
    conn = db.connect(config.resolve(s, "database"))
    try:
        vid = clips.import_file(s, conn, a.video, a.title, a.description, [t for t in (a.hashtags or "").split() if t.startswith("#")] or None)
    except ValueError as e:
        print(f"❌ {e}")
        return 1
    res = squeue.publish_video(s, conn, vid, publish_at=when)
    ok = True
    for r in res:
        good = r["status"] in squeue.GOOD
        ok = ok and good
        print(f"{'✓' if good else '✖'} {r['platform']} : {r['status']}" + (f" — {r['detail'][:160]}" if r.get("detail") and not good else ""))
    return 0 if ok else 1


def cmd_shortcuts(s, a):
    """Crée sur le Bureau des boutons à double-cliquer : « Lancer Piano » (et « Lancer Clips » si cet agent existe)."""
    desk = Path.home() / "Desktop"
    desk.mkdir(exist_ok=True)
    made = []
    for label, inst in (("Lancer Piano", ""), ("Lancer Clips", "clips")):
        if inst and not (config.ROOT / "data" / "instances" / inst).is_dir():
            continue
        f = desk / f"{label}.command"
        f.write_text('#!/bin/bash\ncd "%s" || { echo "Dossier introuvable"; read -n 1 -s -r; exit 1; }\n./p.sh %sui\necho; read -n 1 -s -r -p "L\'agent s\'est arrêté. Appuie sur une touche pour fermer."\n'
                     % (config.ROOT, f"--instance {inst} " if inst else ""))
        f.chmod(0o755)
        made.append(f.name)
    print("✅ Boutons créés sur le Bureau : " + ", ".join(made) + "\n   Premier lancement : clic droit → Ouvrir (macOS demande une confirmation une seule fois).")
    return 0


def cmd_ui_port(s, a):
    print(int((s.get("ui") or {}).get("port", 8765)))
    return 0


def cmd_instance_init(s, a):
    """Crée un autre agent (ex. « clips ») : ses propres données, son profil Chrome, son dossier de vidéos, sa page. L'agent piano n'est pas touché."""
    import json
    import re
    name = re.sub(r"[^a-z0-9_-]", "", a.name.lower())
    if not name:
        print("❌ Nom invalide (lettres, chiffres, - et _).")
        return 1
    base = config.ROOT / "data" / "instances" / name
    base.mkdir(parents=True, exist_ok=True)
    f = base / "local_settings.json"
    cur = json.loads(f.read_text()) if f.exists() else {}
    folder = a.folder or f"~/Desktop/{name.capitalize()}"
    Path(folder).expanduser().mkdir(parents=True, exist_ok=True)
    port = a.port or 8766 + (sum(map(ord, name)) % 50)
    cur.update({"agent": {"kind": "clips"}, "clips": {**cur.get("clips", {}), "folder": folder},
                "inbox": {"watch": []}, "ui": {"port": port}, "songs": {"only_mine": True},
                "autopilot": {"enabled": True, "per_day": 2, "days": 7, **cur.get("autopilot", {})}})      # agent clips : actif d'office, sinon les vidéos déposées ne partent jamais
    if a.profile:
        cur["tiktok"] = {**cur.get("tiktok", {}), "chrome_profile": a.profile}
        cur["youtube"] = {**cur.get("youtube", {}), "chrome_profile": a.profile}
    f.write_text(json.dumps(cur, ensure_ascii=False, indent=1))
    print(f"✅ Agent « {name} » prêt.\n   Dossier de vidéos : {Path(folder).expanduser()}\n   Profil Chrome : {a.profile or '(à choisir : ./p.sh chrome-profiles)'}\n   Page : http://127.0.0.1:{port}")
    print(f"   Lancer : ./p.sh --instance {name} ui")
    return 0


def cmd_youtube_login(s, a):
    from .publisher import youtube_auth
    try:
        youtube_auth.login(config.ROOT / ".env", port=a.port)
    except RuntimeError as e:
        print(f"❌ {e}")
        return 1
    print("✅ YouTube est connecté : les vidéos seront envoyées automatiquement (cochez « Publier ensuite »).")
    return 0


def cmd_tiktok_login(s, a):
    from .publisher import tiktok
    try:
        tiktok.login(config.ROOT / ".env", port=a.port)
    except RuntimeError as e:
        print(f"❌ {e}")
        return 1
    print("✅ TikTok est connecté (mode : " + s.get("tiktok", {}).get("mode", "draft") + ").")
    return 0


def cmd_tiktok_web(s, a):
    """Poste une vidéo sur TikTok en pilotant Safari (compte déjà connecté dans Safari)."""
    from .publisher import tiktok_web
    tiktok_web.BROWSER = {"chrome": "Google Chrome", "safari": "Safari"}[a.browser]
    tiktok_web.PROFILE = a.profile or str(s.get("tiktok", {}).get("chrome_profile", "") or "")
    from .database import db
    video, cap, vid_id, conn = a.video, a.caption, None, None
    if not video:
        conn = db.connect(config.resolve(s, "database"))
        row = conn.execute("SELECT v.output_path, v.meta, s.title, s.artist, v.id FROM videos v LEFT JOIN songs s ON s.id=v.song_id WHERE v.status='READY' AND v.style LIKE '%|vertical' ORDER BY v.id DESC LIMIT 1").fetchone()
        if not row:
            print("❌ Aucune vidéo verticale prête : crée-en une d'abord.")
            return 1
        video = row[0]
        vid_id = row[4]
        import json
        m = json.loads(row[1] or "{}")
        cap = cap or m.get("tiktok_caption") or m.get("description") or m.get("title") or ""
        if row[2] and not a.caption:                 # vidéos déjà créées : hashtags ciblés sur le morceau et le compositeur
            import random
            from .content_generator import generate as g
            body = cap.split(" #")[0]
            cap = body + " " + " ".join(g._tags_for({"title": row[2], "artist": row[3]}, g.LANGS.get(s.get("language", "fr"), g.LANGS["fr"]), random.Random(1)))
    try:
        msg = tiktok_web.post(video, cap, publish=a.post, say=lambda m: print(m))
        print("✅", msg)
        if a.post and conn is not None and vid_id:                       # envoi fait à la main : l'app ne le refera jamais
            from .scheduler import queue
            queue.record_manual(conn, vid_id, "tiktok", "PUBLISHED", msg)
    except Exception as e:
        print(f"❌ {e}")
        return 1
    return 0


def cmd_schedule(s, a):
    """Liste les publications programmées."""
    from .scheduler import queue
    conn = db.connect(config.resolve(s, "database"))
    items = queue.listing(conn)
    for x in items:
        print(f"{x['run_at'].replace('T', ' ')}  {x['status']:<9} {x['format'] or '?':<10} {x['title']}  {x['detail']}")
    print(f"{len(items)} ligne(s) ; {len(queue.unscheduled(conn))} vidéo(s) prête(s) non programmée(s).")
    return 0


def cmd_publish_due(s, a):
    """Publie ce dont l'heure est passée (à lancer toutes les 10 min par launchd si l'interface n'est pas ouverte)."""
    from .scheduler import queue
    conn = db.connect(config.resolve(s, "database"))
    done = queue.run_due(s, conn)
    for d in done:
        print(d)
    print(f"{len(done)} publication(s) traitée(s).")
    return 0 if all(d["status"] != "FAILED" for d in done) else 1


def cmd_publish_now(s, a):
    from .scheduler import queue
    conn = db.connect(config.resolve(s, "database"))
    try:
        for r in queue.publish_video(s, conn, a.video_id):
            print(f"{'✅' if r['status'] in queue.GOOD else '❌'} {r['platform']}: {r['status']} {r['detail']}")
    except RuntimeError as e:
        print(f"❌ {e}")
        return 1
    return 0


def cmd_inbox(s, a):
    """Importe les fichiers MIDI déposés dans data/inbox/."""
    from .music_discovery import inbox
    from .ui.server import import_upload
    st = inbox.status(s)
    print(f"Dossier de réception : {st['path']}  (en attente : {st['waiting']})")
    if a.confirm_rights:
        inbox.set_rights(s, True)
        print("✅ Droits confirmés pour cette boîte de réception.")
    for r in inbox.scan(s, import_upload):
        print(f"  {r['file']}: {r['status']} {r.get('detail', '')}")
    return 0


def cmd_youtube_web(s, a):
    """Poste une vidéo sur YouTube en pilotant YouTube Studio dans Chrome (sans API)."""
    import json
    from .publisher import tiktok_web, youtube_web
    from .publisher.youtube import YouTube
    tiktok_web.BROWSER = "Google Chrome"
    tiktok_web.PROFILE = a.profile or str(s.get("youtube", {}).get("chrome_profile", "") or "")
    conn = db.connect(config.resolve(s, "database"))
    fmt = "horizontal" if a.long else "vertical"
    row = conn.execute("SELECT output_path, meta, id FROM videos WHERE status='READY' AND style LIKE ? ORDER BY id DESC LIMIT 1", (f"%|{fmt}",)).fetchone()
    if not row:
        print(f"❌ Aucune vidéo {fmt} prête (celles déjà envoyées ne sont jamais renvoyées) : crée-en une d'abord.")
        return 1
    m = json.loads(row[1] or "{}")
    m["shorts"] = fmt != "horizontal"
    sn = YouTube.build_snippet({**m, "title": m.get("youtube_title") or m.get("title") or "Piano"}, "public", "10")["snippet"]
    try:
        msg = youtube_web.post(row[0], sn["title"], sn["description"], publish=a.post, say=print)
        print("✅", msg)
        if a.post:                                                       # envoi fait à la main : l'app ne le refera jamais
            from .scheduler import queue
            queue.record_manual(conn, row[2], "youtube", "PUBLISHED", msg)
    except Exception as e:
        print(f"❌ {e}")
        return 1
    return 0


def cmd_clean(s, a):
    """Supprime du disque les vidéos déjà publiées."""
    from .director import cleanup
    conn = db.connect(config.resolve(s, "database"))
    n = cleanup.purge_published(s, conn)
    print(f"🧹 {n} fichier(s)/dossier(s) supprimé(s).")
    return 0


def cmd_chrome_profiles(s, a):
    """Liste les profils Chrome pour choisir celui du compte TikTok."""
    from .publisher import tiktok_web
    profs = tiktok_web.chrome_profiles()
    if not profs:
        print("Aucun profil Chrome trouvé (Chrome est-il installé et lancé au moins une fois ?).")
        return 1
    cur = str(s.get("tiktok", {}).get("chrome_profile", "") or "")
    for p in profs:
        print(f"  {p['dir']:<12} {p['name']:<24} {p['email']}" + ("   ← utilisé" if cur and cur.lower() in (p['dir'].lower(), p['name'].lower(), p['email'].lower()) else ""))
    print("\nPour en choisir un, écris son nom dans config/settings.yaml (tiktok > chrome_profile) ou lance :  ./p.sh tiktok-web --profile \"Nom\"")
    return 0


def cmd_publish_check(s, a):
    """Vérifie pour de vrai les connexions YouTube et TikTok (demande un jeton à chaque plateforme)."""
    from .publisher import adapters
    code = 0
    for ad in adapters(s):
        if hasattr(ad, "check"):
            ok, msg = ad.check()
            print(f"{'✅' if ok else '❌'} {ad.platform:<8} {msg}")
            code |= not ok
    return code


def cmd_mac_install(s, a):
    from .scheduler import launchd
    p = launchd.install(s["publish_times"], config.ROOT)
    print(f"Planification écrite: {p}\nActivez-la avec: launchctl load {p}")
    print("Pour réveiller le Mac aux heures prévues: sudo pmset repeat wakeorpoweron MTWRFSU 08:55:00")
    return 0


def cmd_autostart(s, a):
    """Démarre l'agent tout seul à chaque ouverture de session (et le relance s'il plante). --off pour l'arrêter."""
    import platform
    import subprocess
    from .scheduler import launchd
    if platform.system() != "Darwin":
        print("autostart : réservé au Mac.")
        return 2
    plist = Path.home() / "Library" / "LaunchAgents" / f"{launchd.agent_label(config.instance())}.plist"
    if a.off:
        subprocess.run(["launchctl", "unload", "-w", str(plist)], capture_output=True)
        plist.unlink(missing_ok=True)
        print("✅ Démarrage automatique désactivé.")
        return 0
    p = launchd.install_agent(config.ROOT, instance=config.instance())
    subprocess.run(["launchctl", "unload", str(p)], capture_output=True)
    r = subprocess.run(["launchctl", "load", "-w", str(p)], capture_output=True, text=True)
    if r.returncode:
        print(f"❌ launchctl : {r.stderr.strip()}\nActive-le à la main : launchctl load -w {p}")
        return 1
    print("✅ L'agent démarrera tout seul à chaque ouverture de session (page : http://127.0.0.1:8765).")
    print("Pour qu'il travaille Mac fermé ou en veille, branche-le sur secteur : réglage Batterie > Empêcher la mise en veille automatique.")
    return 0


def not_ready(name):
    def f(s, a):
        print(f"`piano {name}`: pas encore implémenté (voir phases du cahier des charges).")
        return 2
    return f


def main(argv=None):
    p = argparse.ArgumentParser(prog="piano")
    sub = p.add_subparsers(dest="cmd", required=True)
    cmds = {"doctor": cmd_doctor, "status": cmd_status, "queue": cmd_queue, "init": cmd_init}
    for n in ("setup", "start", "stop", "retry", "test"):
        cmds[n] = not_ready(n)
    cmds["import"], cmds["analyze"] = cmd_import, cmd_analyze
    cmds["mac-check"], cmds["mac-install"], cmds["mac-test"] = cmd_mac_check, cmd_mac_install, cmd_mac_test
    cmds["fetch-midi"] = cmd_fetch_midi
    cmds["mac-rec-test"] = cmd_mac_rec_test
    cmds["ui"] = cmd_ui
    cmds["ui-port"], cmds["instance-init"], cmds["post"], cmds["shortcuts"] = cmd_ui_port, cmd_instance_init, cmd_post, cmd_shortcuts
    cmds["autostart"] = cmd_autostart
    cmds["youtube-login"] = cmd_youtube_login
    cmds["publish-check"] = cmd_publish_check
    cmds["tiktok-login"] = cmd_tiktok_login
    cmds["tiktok-web"] = cmd_tiktok_web
    cmds["chrome-profiles"] = cmd_chrome_profiles
    cmds["inbox"] = cmd_inbox
    cmds["clean"] = cmd_clean
    cmds["youtube-web"] = cmd_youtube_web
    cmds["schedule"], cmds["publish-due"], cmds["publish-now"] = cmd_schedule, cmd_publish_due, cmd_publish_now
    cmds["mac-setup"] = cmd_mac_setup
    cmds["auto"] = cmds["run"] = cmds["dry-run"] = cmd_run
    for n in cmds:
        sp = sub.add_parser(n)
        if n == "import":
            sp.add_argument("file"); sp.add_argument("--title", required=True); sp.add_argument("--artist", default="")
            sp.add_argument("--source", required=True); sp.add_argument("--license-proof")
        if n in ("auto", "run", "dry-run"):
            sp.add_argument("--count", type=int, default=1); sp.add_argument("--dry-run", action="store_true", default=(n == "dry-run")); sp.add_argument("--force-synthesia", action="store_true")
        if n in ("youtube-login", "tiktok-login"):
            sp.add_argument("--port", type=int, default=8085)
        if n == "tiktok-web":
            sp.add_argument("--video"); sp.add_argument("--caption", default=""); sp.add_argument("--browser", choices=["chrome", "safari"], default="chrome"); sp.add_argument("--profile", default=""); sp.add_argument("--post", action="store_true", help="clique aussi sur Publier")
        if n == "youtube-web":
            sp.add_argument("--long", action="store_true", help="vidéo horizontale (sinon : la dernière verticale = Short)"); sp.add_argument("--profile", default=""); sp.add_argument("--post", action="store_true")
        if n == "inbox":
            sp.add_argument("--confirm-rights", action="store_true", help="je confirme avoir les droits sur les fichiers reçus")
        if n == "publish-now":
            sp.add_argument("video_id", type=int)
        if n == "ui":
            sp.add_argument("--port", type=int, default=None); sp.add_argument("--no-browser", action="store_true")
        if n == "post":
            sp.add_argument("video"); sp.add_argument("--title", default=""); sp.add_argument("--description", default=""); sp.add_argument("--hashtags", default="")
            sp.add_argument("--at", default="", help="date et heure de mise en ligne, ex. \"2026-10-12 19:00\""); sp.add_argument("--now", action="store_true", help="publier tout de suite")
        if n == "instance-init":
            sp.add_argument("name"); sp.add_argument("--profile", default=""); sp.add_argument("--folder", default=""); sp.add_argument("--port", type=int, default=0)
        if n == "autostart":
            sp.add_argument("--off", action="store_true")
        if n == "analyze":
            sp.add_argument("file"); sp.add_argument("--duration", type=float)
    a = p.parse_args(argv)
    config.load_env()
    s = config.load_settings()
    setup_logging(config.resolve(s, "logs_dir"))
    return cmds[a.cmd](s, a)


if __name__ == "__main__":
    sys.exit(main())
