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
    for _ in range(a.count):
        r = run_one(s, dry_run=a.dry_run)
        print(json.dumps(r, indent=2, ensure_ascii=False, default=str))
        code |= r["status"] not in ("PUBLISHED", "READY", "DRY_RUN")
    return code


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
    cmds["auto"] = cmds["run"] = cmds["dry-run"] = cmd_run
    for n in cmds:
        sp = sub.add_parser(n)
        if n == "import":
            sp.add_argument("file"); sp.add_argument("--title", required=True); sp.add_argument("--artist", default="")
            sp.add_argument("--source", required=True); sp.add_argument("--license-proof")
        if n in ("auto", "run", "dry-run"):
            sp.add_argument("--count", type=int, default=1); sp.add_argument("--dry-run", action="store_true", default=(n == "dry-run"))
        if n == "analyze":
            sp.add_argument("file"); sp.add_argument("--duration", type=float)
    a = p.parse_args(argv)
    s = config.load_settings()
    setup_logging(config.resolve(s, "logs_dir"))
    return cmds[a.cmd](s, a)


if __name__ == "__main__":
    sys.exit(main())
