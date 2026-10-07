import io
import json
import subprocess
import urllib.error
import pytest
from app import config
from app.publisher import adapters
from app.publisher.youtube import YouTube
from app.renderer.thumbnail import make_thumbnail


def fake_http(log, vid="VID123", fail_thumb=False):
    def http(req, timeout=0):
        url = req.full_url
        log.append((req.get_method(), url))
        if "oauth2" in url: return 200, {}, json.dumps({"access_token": "T"}).encode()
        if "uploadType=resumable" in url: log[-1] += (json.loads(req.data),); return 200, {"Location": "https://up/1"}, b""
        if "thumbnails/set" in url:
            if fail_thumb: raise urllib.error.HTTPError(url, 403, "forbidden", {}, io.BytesIO(b"{}"))
            return 200, {}, b"{}"
        return 200, {}, json.dumps({"id": vid}).encode()
    return http


@pytest.fixture(autouse=True)
def creds(monkeypatch):
    for k in ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"):
        monkeypatch.setenv(k, "x")


def video(tmp_path):
    v = tmp_path / "v.mp4"; v.write_bytes(b"x" * 1000); return v


META = {"title": "Clair de Lune - Tu connais ce morceau ?", "description": "Desc", "keywords": ["Clair de Lune", "Debussy", "piano tutorial"],
        "hashtags": ["#piano", "#fyp"], "lang": "fr"}


def test_short_and_long_get_different_titles_and_links(tmp_path):
    log = []
    short = YouTube(fake_http(log)).publish(video(tmp_path), {**META, "shorts": True}, "1")
    sn = next(x for x in log if len(x) == 3)[2]
    assert short.status == "PUBLISHED" and "/shorts/VID123" in short.detail
    assert sn["snippet"]["title"].endswith("#Shorts") and "#Shorts" in sn["snippet"]["description"]
    log.clear()
    long_ = YouTube(fake_http(log)).publish(video(tmp_path), {**META, "shorts": False}, "2")
    ln = next(x for x in log if len(x) == 3)[2]
    assert "watch?v=VID123" in long_.detail and "#Shorts" not in ln["snippet"]["title"] and "#Shorts" not in ln["snippet"]["description"]
    assert ln["snippet"]["categoryId"] == "10" and ln["status"]["selfDeclaredMadeForKids"] is False and ln["snippet"]["defaultLanguage"] == "fr"


def test_tags_stay_within_youtube_limit_and_have_no_duplicates():
    many = {**META, "keywords": [f"mot{i}" * 3 for i in range(200)] + ["Debussy", "debussy"], "shorts": False}
    tags = YouTube.build_snippet(many, "public", "10")["snippet"]["tags"]
    assert sum(len(t) + 1 for t in tags) <= 460 and len({t.lower() for t in tags}) == len(tags)


def test_thumbnail_is_uploaded_for_long_videos_only(tmp_path):
    th = tmp_path / "t.jpg"; th.write_bytes(b"\xff\xd8jpeg")
    log = []
    YouTube(fake_http(log)).publish(video(tmp_path), {**META, "shorts": False, "thumbnail": str(th)}, "1")
    assert any("thumbnails/set" in x[1] for x in log)
    log.clear()
    YouTube(fake_http(log)).publish(video(tmp_path), {**META, "shorts": True, "thumbnail": str(th)}, "1")
    assert not any("thumbnails/set" in x[1] for x in log)


def test_thumbnail_refusal_does_not_lose_the_video(tmp_path):
    th = tmp_path / "t.jpg"; th.write_bytes(b"\xff\xd8jpeg")
    r = YouTube(fake_http([], fail_thumb=True)).publish(video(tmp_path), {**META, "shorts": False, "thumbnail": str(th)}, "1")
    assert r.status == "PUBLISHED" and "miniature non envoyée" in r.detail


def test_quota_error_is_explained(tmp_path):
    body = json.dumps({"error": {"errors": [{"reason": "quotaExceeded"}], "message": "q"}}).encode()
    def http(req, timeout=0):
        if "oauth2" in req.full_url: return 200, {}, json.dumps({"access_token": "T"}).encode()
        raise urllib.error.HTTPError(req.full_url, 403, "x", {}, io.BytesIO(body))
    r = YouTube(http).publish(video(tmp_path), {**META, "shorts": True}, "1")
    assert r.status == "FAILED" and "quota" in r.detail and "demain" in r.detail


def test_check_reports_real_status(monkeypatch):
    assert YouTube(fake_http([])).check() == (True, "connecté")
    monkeypatch.delenv("YOUTUBE_CLIENT_ID")
    ok, msg = YouTube(fake_http([])).check()
    assert not ok and "manquante" in msg
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "x")
    def refused(req, timeout=0): raise urllib.error.HTTPError(req.full_url, 400, "bad", {}, io.BytesIO(b"{}"))
    ok, msg = YouTube(refused).check()
    assert not ok and "youtube-login" in msg


def test_each_format_goes_only_where_it_belongs(tmp_path):
    s = config.load_settings(); s["paths"] = {**s["paths"], "data_dir": str(tmp_path)}
    vertical = [getattr(a, "platform", "") for a in adapters(s, fmt="vertical")]
    horizontal = [getattr(a, "platform", "") for a in adapters(s, fmt="horizontal")]
    assert "youtube" in vertical and "tiktok" in vertical
    assert "youtube" in horizontal and "tiktok" not in horizontal            # TikTok : vertical uniquement


def test_thumbnail_is_a_real_jpeg_of_the_right_size_with_the_title(tmp_path):
    from PIL import Image
    v = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=1920x1080:rate=10:duration=6", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(v)], check=True)
    out = make_thumbnail(v, tmp_path / "t.jpg", "Clair de Lune", "C. Debussy")
    im = Image.open(out)
    assert im.size == (1280, 720) and im.format == "JPEG" and out.stat().st_size < 2_000_000
    import numpy as np
    arr = np.asarray(im.convert("L"), dtype=float)
    assert arr[560:700].mean() < arr[20:160].mean()                                  # voile sombre en bas : le titre reste lisible
    vv = tmp_path / "vv.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=10:duration=6", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(vv)], check=True)
    assert Image.open(make_thumbnail(vv, tmp_path / "tv.jpg", "Für Elise")).size == (1080, 1920)


def test_pipeline_creates_thumbnail_and_publishes_per_format(tmp_path, monkeypatch):
    from app.director import pipeline
    st = config.load_settings()
    st["paths"] = {**st["paths"], "data_dir": str(tmp_path / "d"), "database": str(tmp_path / "db.sqlite3"), "logs_dir": str(tmp_path / "l")}
    st["duration_target"], st["duration_range"], st["engine"] = 6, [4, 8], "builtin"
    st["formats"]["vertical"]["min_duration"] = 0
    got = []
    class Spy:
        platform = "spy"
        def publish(self, video, meta, key):
            got.append((meta["format"], meta.get("thumbnail"))); 
            from app.publisher.base import Result
            return Result("spy", "PUBLISHED", "id", "https://example.com/v")
    monkeypatch.setattr(pipeline, "adapters", lambda s, fmt=None: [Spy()])
    r = pipeline.run_one(st, seed=6, publish=True, level="moyen", formats=["vertical"])
    assert r["status"] == "PUBLISHED" and r["post"]["thumbnail"].endswith(".jpg")
    assert got and got[0][0] == "vertical" and got[0][1] and open(got[0][1], "rb").read(2) == b"\xff\xd8"


def test_page_and_api_offer_connection_test(tmp_path):
    from app.ui.page import PAGE
    assert "Tester mes connexions" in PAGE and "/api/check-platforms" in PAGE and "Miniature" in PAGE


def test_thumbnail_drops_the_banner_so_the_title_is_not_doubled(tmp_path):
    from PIL import Image
    v = tmp_path / "v.mp4"                             # vidéo montée : bandeau ROUGE en haut (150 px) puis le contenu
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "color=c=0x303030:s=1920x1080:r=10:d=6,drawbox=x=0:y=0:w=1920:h=150:color=red:t=fill", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(v)], check=True)
    out = make_thumbnail(v, tmp_path / "t.jpg", "Titre", "Compositeur", top_crop=150)
    r, g, b = Image.open(out).convert("RGB").getpixel((640, 12))
    assert not (r > 180 and g < 80 and b < 80)           # plus de rouge en haut : le bandeau a été retiré
    r2, g2, b2 = make_thumbnail(v, tmp_path / "t2.jpg", "Titre", "", top_crop=0) and Image.open(tmp_path / "t2.jpg").convert("RGB").getpixel((640, 12))
    assert r2 > 180 and g2 < 80                          # sans recadrage, il serait resté
