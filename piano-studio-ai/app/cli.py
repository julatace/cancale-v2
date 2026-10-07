import argparse
import sys

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


def cmd_mac_install(s, a):
    from .scheduler import launchd
    p = launchd.install(s["publish_times"], config.ROOT)
    print(f"Planification écrite: {p}\nActivez-la avec: launchctl load {p}")
    print("Pour réveiller le Mac aux heures prévues: sudo pmset repeat wakeorpoweron MTWRFSU 08:55:00")
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
    cmds["auto"] = cmds["run"] = cmds["dry-run"] = cmd_run
    for n in cmds:
        sp = sub.add_parser(n)
        if n == "import":
            sp.add_argument("file"); sp.add_argument("--title", required=True); sp.add_argument("--artist", default="")
            sp.add_argument("--source", required=True); sp.add_argument("--license-proof")
        if n in ("auto", "run", "dry-run"):
            sp.add_argument("--count", type=int, default=1); sp.add_argument("--dry-run", action="store_true", default=(n == "dry-run")); sp.add_argument("--force-synthesia", action="store_true")
        if n == "analyze":
            sp.add_argument("file"); sp.add_argument("--duration", type=float)
    a = p.parse_args(argv)
    s = config.load_settings()
    setup_logging(config.resolve(s, "logs_dir"))
    return cmds[a.cmd](s, a)


if __name__ == "__main__":
    sys.exit(main())
