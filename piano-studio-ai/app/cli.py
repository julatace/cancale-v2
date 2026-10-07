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


def not_ready(name):
    def f(s, a):
        print(f"`piano {name}`: pas encore implémenté (voir phases du cahier des charges).")
        return 2
    return f


def main(argv=None):
    p = argparse.ArgumentParser(prog="piano")
    sub = p.add_subparsers(dest="cmd", required=True)
    cmds = {"doctor": cmd_doctor, "status": cmd_status, "queue": cmd_queue, "init": cmd_init}
    for n in ("setup", "start", "stop", "retry", "test", "auto", "dry-run"):
        cmds[n] = not_ready(n)
    for n in cmds:
        sub.add_parser(n)
    a = p.parse_args(argv)
    s = config.load_settings()
    setup_logging(config.resolve(s, "logs_dir"))
    return cmds[a.cmd](s, a)


if __name__ == "__main__":
    sys.exit(main())
