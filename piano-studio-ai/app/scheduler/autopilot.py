"""Pilote automatique : garde l'agenda rempli tout seul.
Chaque jour de la fenêtre doit avoir `per_day` vidéos DÉJÀ programmées dans TikTok/YouTube ; ce qui manque est fabriqué (une vidéo à la fois,
comme d'habitude) puis programmé nativement. Jamais de publication immédiate, jamais de doublon : on ne fabrique que le manque."""
import time
from datetime import datetime, timedelta, timezone

from . import queue as squeue

BACKOFF_MIN = 30
BACKOFF_MAX_H = 6


def conf(s) -> dict:
    c = {"enabled": False, "per_day": 2, "days": 7, "times": "12:30, 19:00", **(s.get("autopilot") or {})}
    c["per_day"] = max(1, min(int(c["per_day"]), 4))
    c["days"] = max(1, min(int(c["days"]), squeue.MAX_LEAD_DAYS - 1))
    return c


def scheduled_by_day(conn, now: datetime) -> dict:
    """Vidéos déjà programmées dans les réseaux (traces « DONE » à venir), par jour local."""
    rows = conn.execute("SELECT run_at FROM schedule WHERE status='DONE' AND run_at>?", (squeue._utc(now),)).fetchall()
    out = {}
    for r in rows:
        d = datetime.fromisoformat(r["run_at"]).astimezone().date().isoformat()
        out[d] = out.get(d, 0) + 1
    return out


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


class AutoPilot:
    """État en mémoire : pause progressive après un échec, pour ne jamais boucler en refabriquant sans fin."""

    def __init__(self, clock=time.time):
        self.clock = clock
        self.fails = 0
        self.next_try = 0.0
        self.running = False
        self.message = ""
        self.last_run = None

    def status(self, s, conn, songs_waiting: int) -> dict:
        c = conf(s)
        miss = deficit(s, conn) if c["enabled"] else []
        return {**c, "missing": sum(m["count"] for m in miss), "message": self.message, "paused_until": self.next_try if self.next_try > self.clock() else None,
                "songs": songs_waiting, "last_run": self.last_run}

    def decide(self, s, conn, job_idle: bool, songs_waiting: int, now=None):
        """Retourne la liste des jours à fabriquer, ou None (avec self.message qui explique pourquoi)."""
        c = conf(s)
        if not c["enabled"]:
            self.message = ""
            return None
        if not job_idle:
            return None
        if self.clock() < self.next_try:
            self.message = "En pause après un souci : nouvel essai automatique plus tard."
            return None
        miss = deficit(s, conn, now)
        if not miss:
            self.message = f"✓ Agenda complet sur {c['days']} jours ({c['per_day']}/jour). Je surveille."
            return None
        if songs_waiting <= 0:
            self.message = "En attente de nouveaux morceaux dans ton dossier MIDI."
            return None
        self.message = f"Il manque {sum(m['count'] for m in miss)} vidéo(s) : fabrication en cours…"
        return miss

    def started(self):
        self.running = True
        self.last_run = self.clock()

    def finished(self, planned: int, failed: bool):
        """Appelé à la fin d'une fabrication lancée par le pilote."""
        self.running = False
        if planned > 0 and not failed:
            self.fails, self.next_try = 0, 0.0
            return
        self.fails += 1
        wait = min(BACKOFF_MIN * 60 * 2 ** (self.fails - 1), BACKOFF_MAX_H * 3600)
        self.next_try = self.clock() + wait
        self.message = "Souci pendant la fabrication : pause avant le prochain essai."
