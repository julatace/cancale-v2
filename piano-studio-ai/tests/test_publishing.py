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


def test_tiktok_web_flow_prepares_without_publishing(tmp_path, monkeypatch):
    from app.publisher import tiktok_web as tw
    v = tmp_path / "v.mp4"; v.write_bytes(b"x")
    calls = []
    monkeypatch.setattr(tw, "_osa", lambda s, timeout=30: calls.append(s) or "")
    monkeypatch.setattr(tw, "_js", lambda c: calls.append(c) or ("false" if "connecter" in c else "true"))
    monkeypatch.setattr(tw, "_keys", lambda *l: calls.append("keys"))
    monkeypatch.setattr(tw, "_clip", lambda t: calls.append("clip:" + t[:5]))
    monkeypatch.setattr(tw, "_real_click_upload", lambda say: calls.append("click"))
    monkeypatch.setattr(tw.time, "sleep", lambda s: None)
    out = tw.post(v, "légende #piano", publish=False)
    assert "non publié" in out and not any("publier|post" in str(c) for c in calls)
    assert tw.post(v, "x", publish=True) == "publié"


def test_tiktok_web_splits_caption_and_hashtags():
    from app.publisher.tiktok_web import split_caption
    body, tags = split_caption("Ça sonne bien Invention 8 - J. S. Bach #piano #pourtoi #Musique #piano #été")
    assert body == "Ça sonne bien Invention 8 - J. S. Bach"
    assert tags == ["#piano", "#pourtoi", "#Musique", "#ete"]


def test_hashtags_are_targeted_on_song_and_composer():
    from app.content_generator.generate import generate
    c = generate({"title": "Invention 8", "artist": "J. S. Bach"}, "Facile", 3, set(), 80)
    assert c["hashtags"][:4] == ["#pianocover", "#pianotutorial", "#easypiano", "#piano"]
    assert "#bach" in c["hashtags"] and "#invention8" in c["hashtags"] and len(c["hashtags"]) <= 6


def test_youtube_native_scheduling_sets_publish_at():
    from app.publisher.youtube import YouTube
    sn = YouTube.build_snippet({"title": "T", "description": "d", "hashtags": [], "publish_at": "2030-01-06T17:00:00Z"}, "public", "10")
    assert sn["status"]["privacyStatus"] == "private" and sn["status"]["publishAt"] == "2030-01-06T17:00:00Z"
    assert YouTube.build_snippet({"title": "T", "description": "d", "hashtags": []}, "public", "10")["status"]["privacyStatus"] == "public"


def test_chrome_profile_resolution(tmp_path, monkeypatch):
    from app.publisher import tiktok_web as tw
    d = tmp_path / "Library/Application Support/Google/Chrome"; d.mkdir(parents=True)
    (d / "Local State").write_text('{"profile":{"info_cache":{"Default":{"name":"Julien","user_name":"a@b.c"},"Profile 2":{"name":"Piano","user_name":""}}}}')
    monkeypatch.setattr(tw.Path, "home", staticmethod(lambda: tmp_path))
    assert tw.resolve_profile("piano") == "Profile 2" and tw.resolve_profile("A@B.C") == "Default" and tw.resolve_profile("") == ""
    import pytest
    with pytest.raises(RuntimeError, match="introuvable"):
        tw.resolve_profile("nope")


def test_youtube_web_flow_without_api(tmp_path, monkeypatch):
    from app.publisher import tiktok_web as tw, youtube_web as yw
    v = tmp_path / "v.mp4"; v.write_bytes(b"x")
    calls = []
    monkeypatch.setattr(tw, "_osa", lambda s, timeout=30: calls.append(s) or "")
    monkeypatch.setattr(tw, "_js", lambda c: calls.append(c) or ("false" if "accounts.google" in c else "https://youtu.be/abc" if "youtu.be" in c else "true"))
    monkeypatch.setattr(tw, "_keys", lambda *l: calls.append("keys"))
    monkeypatch.setattr(tw, "_clip", lambda t: calls.append("clip:" + t[:12]))
    monkeypatch.setattr(tw, "choose_file", lambda p, say, **k: calls.append("file"))
    monkeypatch.setattr(yw, "_paste_into", lambda sel, txt: calls.append(("text", sel, txt)))
    monkeypatch.setattr(yw.time, "sleep", lambda s: None)
    assert "non publié" in yw.post(v, "Titre", "Desc", publish=False)
    assert not any("done-button" in str(c) and "click" in str(c) for c in calls)
    assert yw.post(v, "Titre", "Desc", publish=True) == "https://youtu.be/abc"


def test_queue_marks_horizontal_as_normal_youtube_video_and_forces_web_publish(tmp_path, monkeypatch):
    from app.database import db
    from app.scheduler import queue
    import app.publisher as pubs
    c = db.connect(tmp_path / "t.sqlite3")
    db.add_song(c, "A", "x", "s", "LEGAL_CONFIRMED", hash="a")
    f = tmp_path / "v.mp4"; f.write_bytes(b"x")
    c.execute("INSERT INTO videos(song_id,style,duration,output_path,quality_score,status,title,meta,created_at) VALUES(1,'facile|horizontal',90,?,95,'READY','T','{}',?)", (str(f), db.now()))
    c.commit()
    seen = {}

    class Fake:
        platform = "youtube"
        def publish(self, video, meta, key):
            seen["shorts"] = meta["shorts"]
            from app.publisher.base import Result
            return Result("youtube", "PUBLISHED", key, "ok")

    def fake_adapters(s, fmt=None):
        seen["web_publish"] = (s["youtube"]["web_publish"], s["tiktok"]["web_publish"])
        return [Fake()]
    import app.scheduler.queue as q
    monkeypatch.setattr(pubs, "adapters", fake_adapters)
    res = q.publish_video({"youtube": {"mode": "web"}, "tiktok": {"mode": "web"}}, c, 1)
    assert res[0]["status"] == "PUBLISHED" and seen["shorts"] is False and seen["web_publish"] == (True, True)


def test_choose_file_never_types_when_the_open_dialog_is_missing(monkeypatch):
    import pytest
    from app.publisher import tiktok_web as tw
    typed = []
    monkeypatch.setattr(tw, "_js", lambda c: "500,400")
    monkeypatch.setattr(tw, "_sheet_open", lambda: False)
    monkeypatch.setattr(tw, "_keys", lambda *l: typed.append(l))
    monkeypatch.setattr(tw, "_clip", lambda t: typed.append(t))
    monkeypatch.setattr(tw.subprocess, "run", lambda *a, **k: None)
    monkeypatch.setattr(tw.shutil if hasattr(tw, "shutil") else __import__("shutil"), "which", lambda n: "/usr/bin/" + n)
    monkeypatch.setattr(tw.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError, match="ne s'est pas ouverte"):
        tw._real_click_upload(lambda m: None)
    assert typed == []                                   # rien n'est tapé dans la page (c'est ce qui ouvrait la barre de recherche de Chrome)


def test_inject_file_sends_the_whole_file_in_small_chunks_without_dialog(tmp_path, monkeypatch):
    import base64
    from app.publisher import tiktok_web as tw
    v = tmp_path / "v.mp4"; v.write_bytes(bytes(range(256)) * 3000)             # 768 Ko
    calls = []
    monkeypatch.setattr(tw, "_js", lambda c: calls.append(c) or "true")
    monkeypatch.setattr(tw, "_real_click_upload", lambda say: calls.append("DIALOG"))
    tw.choose_file(v, lambda m: None)
    pushes = [c for c in calls if c.startswith("window.__pf.push")]
    assert "DIALOG" not in calls and len(pushes) >= 3 and all(len(c) < 250_000 for c in calls)
    joined = "".join(c.split('"')[1] for c in pushes)
    assert base64.b64decode(joined) == v.read_bytes()


def test_choose_file_falls_back_to_the_open_dialog_if_injection_fails(tmp_path, monkeypatch):
    from app.publisher import tiktok_web as tw
    v = tmp_path / "v.mp4"; v.write_bytes(b"x")
    seen = []
    monkeypatch.setattr(tw, "_js", lambda c: "false")
    monkeypatch.setattr(tw, "_real_click_upload", lambda say, strict=True: seen.append("click"))
    monkeypatch.setattr(tw, "_keys", lambda *l: seen.append("keys"))
    monkeypatch.setattr(tw, "_clip", lambda t: seen.append("clip"))
    monkeypatch.setattr(tw.time, "sleep", lambda s: None)
    tw.choose_file(v, lambda m: None)
    assert seen[0] == "click" and "keys" in seen


def test_encode_falls_back_to_simple_export_if_ffmpeg_refuses_an_option(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from app.renderer import compose
    out = tmp_path / "o.mp4"; calls = []

    def fake_run(cmd, **k):
        calls.append(cmd)
        if len(calls) == 1:
            return SimpleNamespace(returncode=1, stderr="Unrecognized option 'fps_mode'")
        out.write_bytes(b"x" * 10)
        return SimpleNamespace(returncode=0, stderr="")
    monkeypatch.setattr(compose.subprocess, "run", fake_run)
    r = compose._encode(["ffmpeg", "-i", "a"], 60, 30, out)
    assert r.returncode == 0 and "-fps_mode" in calls[0] and "-fps_mode" not in calls[1] and "-af" not in calls[1]


def test_refused_video_says_why(tmp_path):
    import sqlite3
    from app import config
    from app.database import db
    from app.director import pipeline
    st = config.load_settings()
    st["paths"] = {**st["paths"], "data_dir": str(tmp_path), "database": str(tmp_path / "d.sqlite3"), "logs_dir": str(tmp_path / "l")}
    conn = db.connect(tmp_path / "d.sqlite3")
    db.add_song(conn, "A", "x", "s", "LEGAL_CONFIRMED", hash="a")
    rep = {}
    F = st["formats"]["vertical"]
    r = pipeline._finalize(st, conn, 1, "facile", "vertical", F, tmp_path / "v.mp4", {"duration": 60}, {"title": "T", "description": "d"}, rep, False,
                           {"score": 60, "issues": ["image figée", "écran noir"]})
    assert r["status"] == "FAILED" and "image figée" in r["error"] and "60/100" in r["error"]


def test_choose_file_uses_the_open_dialog_when_the_page_ignores_the_direct_send(tmp_path, monkeypatch):
    from app.publisher import tiktok_web as tw
    v = tmp_path / "v.mp4"; v.write_bytes(b"x")
    seen = []

    def js(code):
        if "contenteditable" in code:
            return "false"                                   # la page ne réagit jamais à l'injection
        return "true"
    monkeypatch.setattr(tw, "_js", js)
    monkeypatch.setattr(tw, "_real_click_upload", lambda say, strict=True: seen.append(("click", strict)))
    monkeypatch.setattr(tw, "_keys", lambda *l: seen.append("keys"))
    monkeypatch.setattr(tw, "_clip", lambda t: seen.append("clip"))
    t = {"v": 0.0}
    monkeypatch.setattr(tw.time, "monotonic", lambda: t["v"])
    monkeypatch.setattr(tw.time, "sleep", lambda s: t.__setitem__("v", t["v"] + s))
    tw.choose_file(v, lambda m: None, verify='String(!!document.querySelector("[contenteditable=true]"))', wait=10)
    assert ("click", False) in seen and "keys" in seen                  # plan B lancé, sans exiger la détection de la fenêtre


def test_choose_file_stops_after_injection_when_the_page_reacts(tmp_path, monkeypatch):
    from app.publisher import tiktok_web as tw
    v = tmp_path / "v.mp4"; v.write_bytes(b"x")
    seen = []
    monkeypatch.setattr(tw, "_js", lambda c: "true")
    monkeypatch.setattr(tw, "_real_click_upload", lambda say, strict=True: seen.append("click"))
    monkeypatch.setattr(tw.time, "sleep", lambda s: None)
    tw.choose_file(v, lambda m: None, verify="x", wait=10)
    assert seen == []


def test_tiktok_uses_the_configured_chrome_profile_and_explains_when_no_window(monkeypatch):
    import pytest
    from app import config
    from app.publisher import adapters, tiktok_web as tw
    s = config.load_settings()
    assert s["tiktok"]["chrome_profile"] == "angeled92"
    tk = [a for a in adapters(s) if a.platform == "tiktok"][0]
    assert tk.profile == "angeled92"                               # le profil du compte est transmis à l'adaptateur
    monkeypatch.setattr(tw, "PROFILE", "")
    monkeypatch.setattr(tw, "BROWSER", "Google Chrome")
    monkeypatch.setattr(tw, "_osa", lambda s_, timeout=30: (_ for _ in ()).throw(RuntimeError("Can't get window 1")) if "set URL" in s_ else "")
    monkeypatch.setattr(tw, "_js", lambda c: "2")
    monkeypatch.setattr(tw, "chrome_profiles", lambda: [{"dir": "Default", "name": "angeled92", "email": ""}])
    with pytest.raises(RuntimeError, match="chrome_profile.*angeled92"):
        tw.open_url("https://x", lambda m: None, "TikTok")


def test_page_is_opened_in_the_profile_before_testing_javascript(monkeypatch):
    from app.publisher import tiktok_web as tw
    order = []
    monkeypatch.setattr(tw, "PROFILE", "angeled92")
    monkeypatch.setattr(tw, "BROWSER", "Google Chrome")
    monkeypatch.setattr(tw, "chrome_profiles", lambda: [{"dir": "Profile 3", "name": "angeled92", "email": ""}])
    monkeypatch.setattr(tw.subprocess, "run", lambda cmd, **k: order.append(("open", cmd)))
    monkeypatch.setattr(tw, "_osa", lambda s, timeout=30: order.append(("osa", s)) or "")
    monkeypatch.setattr(tw, "_js", lambda c: order.append(("js", c)) or "true")
    monkeypatch.setattr(tw.time, "sleep", lambda s: None)
    tw.open_url("https://www.tiktok.com/tiktokstudio/upload", lambda m: None, "TikTok Studio")
    kinds = [k for k, _ in order]
    assert kinds.index("open") < kinds.index("js")                                   # d'abord la fenêtre du bon profil, ensuite le test JavaScript
    cmd = order[kinds.index("open")][1]
    assert cmd[:3] == ["open", "-na", "Google Chrome"] and "--profile-directory=Profile 3" in cmd


def test_youtube_also_opens_the_angeled92_profile():
    from app import config
    from app.publisher import adapters
    s = config.load_settings()
    yt = [a for a in adapters(s) if a.platform == "youtube"][0]
    assert yt.profile == "angeled92"


def test_youtube_text_is_typed_into_the_page_and_checked(monkeypatch):
    import json
    import pytest
    from app.publisher import tiktok_web as tw, youtube_web as yw
    js = yw._insert_js("#title-textarea #textbox", 'Ça "marche"\nligne 2')
    assert json.dumps('Ça "marche"\nligne 2') in js and "insertLineBreak" in js and "selectAll" in js      # texte protégé, retours à la ligne gérés
    assert yw._same("Titre  de   la vidéo", "Titre de la vidéo") and not yw._same("25_1791399483_vertical.mp4", "Invention 8 - Bach")
    calls = []
    monkeypatch.setattr(tw, "_js", lambda c: "Invention 8 - Bach" if "insertText" in c else "true")
    monkeypatch.setattr(tw, "_keys", lambda *a: calls.append("keys"))
    monkeypatch.setattr(tw, "_clip", lambda t: calls.append("clip"))
    monkeypatch.setattr(yw.time, "sleep", lambda s: None)
    yw._paste_into("#title-textarea #textbox", "Invention 8 - Bach")
    assert calls == []                                                          # la saisie directe a suffi : pas de presse-papiers
    monkeypatch.setattr(tw, "_js", lambda c: "true" if ("selectAll" in c and "insertText" not in c) else "25_1791_vertical.mp4")             # la page garde l'ancien nom : on essaie le presse-papiers, puis on échoue clairement
    with pytest.raises(RuntimeError, match="n'a pas été écrit"):
        yw._paste_into("#title-textarea #textbox", "Invention 8 - Bach")
    assert calls == ["clip", "keys"]


def test_youtube_short_can_be_switched_off_and_only_the_horizontal_video_goes():
    from app import config
    from app.publisher import adapters
    s = config.load_settings()
    names = lambda fmt: sorted(a.platform for a in adapters(s, fmt=fmt))
    assert "youtube" in names("vertical") and "youtube" in names("horizontal")        # par défaut : Short + vidéo normale
    s["youtube"] = {**s["youtube"], "shorts": False}
    assert "youtube" not in names("vertical") and "tiktok" in names("vertical")        # plus de Short, TikTok continue
    assert "youtube" in names("horizontal")                                            # la vidéo horizontale part toujours sur YouTube
