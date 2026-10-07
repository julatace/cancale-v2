import sqlite3
from app import config
from app.database import db
from app.director import pipeline
from app.ui import server


def settings(tmp_path):
    st = config.load_settings()
    st["paths"] = {**st["paths"], "data_dir": str(tmp_path / "d"), "database": str(tmp_path / "db.sqlite3"), "logs_dir": str(tmp_path / "l")}
    st["duration_target"], st["duration_range"], st["engine"] = 6, [4, 8], "builtin"
    st["formats"]["vertical"]["min_duration"] = 0
    return st


def test_old_database_without_meta_column_is_upgraded(tmp_path):
    path = tmp_path / "old.sqlite3"
    c = sqlite3.connect(path)
    c.executescript("CREATE TABLE videos(id INTEGER PRIMARY KEY, song_id INT, style TEXT, duration REAL, output_path TEXT, quality_score REAL, status TEXT, video_hash TEXT, title TEXT, created_at TEXT NOT NULL);")
    c.commit(); c.close()
    conn = db.connect(path)
    assert "meta" in {r[1] for r in conn.execute("PRAGMA table_info(videos)")}


def test_video_report_and_history_carry_the_texts_to_copy(tmp_path):
    st = settings(tmp_path)
    r = pipeline.run_one(st, seed=8, publish=False, level="moyen", formats=["vertical"])
    post = r["post"]
    assert post["tiktok_caption"] and post["instagram_caption"] and post["youtube_title"] and post["description"] and post["hashtags"]
    h = server.videos(st)[0]
    assert h["post"]["title"] == r["title"] and h["file"]


def test_page_has_copy_buttons_and_platform_links():
    from app.ui.page import PAGE
    for needle in ("Copier le texte TikTok", "Copier le texte Instagram", "Copier le titre YouTube", "tiktok.com/upload", "studio.youtube.com", "clipboard"):
        assert needle in PAGE
