import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS songs(
  id INTEGER PRIMARY KEY, title TEXT NOT NULL, artist TEXT, source TEXT,
  license TEXT NOT NULL DEFAULT 'UNKNOWN', midi_path TEXT, hash TEXT UNIQUE,
  created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS videos(
  id INTEGER PRIMARY KEY, song_id INTEGER REFERENCES songs(id), style TEXT,
  duration REAL, output_path TEXT, quality_score REAL, status TEXT, video_hash TEXT UNIQUE,
  title TEXT, meta TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS publications(
  id INTEGER PRIMARY KEY, video_id INTEGER REFERENCES videos(id), platform TEXT,
  post_id TEXT, status TEXT, published_at TEXT,
  UNIQUE(video_id, platform));
CREATE TABLE IF NOT EXISTS analytics(
  id INTEGER PRIMARY KEY, publication_id INTEGER REFERENCES publications(id),
  views INT, likes INT, comments INT, shares INT, saves INT,
  watch_time REAL, completion_rate REAL, collected_at TEXT);
CREATE TABLE IF NOT EXISTS errors(
  id INTEGER PRIMARY KEY, stage TEXT, message TEXT, severity TEXT,
  timestamp TEXT, retry_count INT DEFAULT 0);
"""

LICENSES = ("LEGAL_CONFIRMED", "LICENSE_REVIEW", "UNKNOWN", "REJECTED")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def connect(path) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(videos)")}
    if "meta" not in cols:                                   # bases créées avant l'ajout des textes de publication
        conn.execute("ALTER TABLE videos ADD COLUMN meta TEXT")
        conn.commit()
    return conn


def add_song(conn, title, artist, source, license, midi_path=None, hash=None) -> int:
    if license not in LICENSES:
        raise ValueError(f"licence invalide: {license}")
    cur = conn.execute(
        "INSERT INTO songs(title,artist,source,license,midi_path,hash,created_at) VALUES(?,?,?,?,?,?,?)",
        (title, artist, source, license, str(midi_path) if midi_path else None, hash, now()))
    conn.commit()
    return cur.lastrowid


def song_usable(conn, song_id, cooldown_days) -> tuple[bool, str]:
    """Garde-fou légal + anti-duplication: seul LEGAL_CONFIRMED entre dans le pipeline."""
    row = conn.execute("SELECT license FROM songs WHERE id=?", (song_id,)).fetchone()
    if row is None:
        return False, "morceau inconnu"
    if row["license"] != "LEGAL_CONFIRMED":
        return False, f"licence {row['license']} -> SKIP SONG"
    since = (datetime.now(timezone.utc) - timedelta(days=cooldown_days)).isoformat()
    used = conn.execute("SELECT 1 FROM videos WHERE song_id=? AND created_at>=? LIMIT 1",
                        (song_id, since)).fetchone()
    if used:
        return False, f"déjà utilisé dans les {cooldown_days} derniers jours"
    return True, "ok"


def log_error(conn, stage, message, severity="ERROR", retry_count=0):
    conn.execute("INSERT INTO errors(stage,message,severity,timestamp,retry_count) VALUES(?,?,?,?,?)",
                 (stage, message, severity, now(), retry_count))
    conn.commit()
