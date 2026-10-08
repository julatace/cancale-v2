import json
import pytest
from app.publisher import tiktok
from app.publisher.base import Result

META = {"title": "Titre", "tiktok_caption": "Légende #piano"}


class Fake:
    """Faux TikTok : enregistre les appels et répond comme l'API documentée."""
    def __init__(self, creator_opts=("SELF_ONLY",), status="PUBLISH_COMPLETE", token_ok=True):
        self.calls, self.opts, self.status, self.token_ok = [], list(creator_opts), status, token_ok

    def __call__(self, req, timeout=0):
        url = req.full_url
        body = req.data
        self.calls.append((req.get_method(), url.replace(tiktok.API, ""), body, dict(req.headers)))
        if url.endswith("/oauth/token/"):
            return 200, {}, json.dumps({"access_token": "AT"} if self.token_ok else {"error": "invalid_grant"}).encode()
        if "creator_info" in url:
            return 200, {}, json.dumps({"data": {"privacy_level_options": self.opts}, "error": {"code": "ok"}}).encode()
        if url.endswith("/init/"):
            return 200, {}, json.dumps({"data": {"publish_id": "P1", "upload_url": "https://upload.example/u"}, "error": {"code": "ok"}}).encode()
        if "status/fetch" in url:
            return 200, {}, json.dumps({"data": {"status": self.status}, "error": {"code": "ok"}}).encode()
        return 200, {}, b""                                              # envoi de la vidéo


@pytest.fixture
def video(tmp_path):
    v = tmp_path / "v.mp4"; v.write_bytes(b"x" * 300_000); return v


@pytest.fixture(autouse=True)
def creds(monkeypatch):
    for k in ("TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET", "TIKTOK_REFRESH_TOKEN"):
        monkeypatch.setenv(k, "x")


def test_draft_mode_sends_to_inbox_with_the_right_upload_headers(video):
    f = Fake()
    r = tiktok.TikTok(f, mode="draft", sleep=lambda s: None).publish(video, META, "1")
    assert r.status == "DRAFT" and r.post_id == "P1" and "Publier" in r.detail
    paths = [c[1] for c in f.calls]
    assert any("inbox/video/init" in p for p in paths) and not any("creator_info" in p for p in paths)
    put = next(c for c in f.calls if c[0] == "PUT")
    assert put[3]["Content-range"] == "bytes 0-299999/300000" and put[3]["Content-type"] == "video/mp4"
    init = json.loads(next(c for c in f.calls if "inbox/video/init" in c[1])[2])
    assert init["source_info"] == {"source": "FILE_UPLOAD", "video_size": 300000, "chunk_size": 300000, "total_chunk_count": 1}


def test_direct_mode_uses_the_most_open_allowed_privacy(video):
    f = Fake(creator_opts=("SELF_ONLY",))                               # app non approuvée : privé seulement
    r = tiktok.TikTok(f, mode="direct", sleep=lambda s: None).publish(video, META, "1")
    assert r.status == "PUBLISHED" and "SELF_ONLY" in r.detail
    post = json.loads(next(c for c in f.calls if c[1].endswith("/video/init/"))[2])
    assert post["post_info"]["title"] == "Légende #piano" and post["post_info"]["privacy_level"] == "SELF_ONLY"
    r2 = tiktok.TikTok(Fake(creator_opts=("PUBLIC_TO_EVERYONE", "SELF_ONLY")), mode="direct", sleep=lambda s: None).publish(video, META, "1")
    assert "PUBLIC_TO_EVERYONE" in r2.detail


def test_missing_credentials_and_bad_token_are_reported_not_raised(video, monkeypatch):
    monkeypatch.delenv("TIKTOK_CLIENT_KEY")
    assert tiktok.TikTok(Fake()).publish(video, META, "1").status == "NOT_CONFIGURED"
    monkeypatch.setenv("TIKTOK_CLIENT_KEY", "x")
    r = tiktok.TikTok(Fake(token_ok=False)).publish(video, META, "1")
    assert r.status == "FAILED" and "tiktok-login" in r.detail


def test_network_failure_does_not_crash_the_pipeline(video):
    def boom(req, timeout=0): raise OSError("réseau coupé")
    assert tiktok.TikTok(boom).publish(video, META, "1").status == "FAILED"


def test_big_videos_are_sent_in_chunks(tmp_path):
    big = tmp_path / "big.mp4"; big.write_bytes(b"y" * (61 * 1024 * 1024))
    f = Fake()
    tiktok.TikTok(f, mode="draft", sleep=lambda s: None).publish(big, META, "1")
    assert len([c for c in f.calls if c[0] == "PUT"]) == 3             # 61 Mo -> 30 + 30 + 1 Mo


def test_login_flow_with_simulated_tiktok(tmp_path, monkeypatch):
    import threading, time, urllib.request
    seen = {}
    def fake_http(req, timeout=0):
        seen["body"] = req.data.decode()
        return 200, {}, json.dumps({"access_token": "A", "refresh_token": "RT-TIK"}).encode()
    def user_clicks_allow():
        time.sleep(0.5)
        for _ in range(40):
            try: urllib.request.urlopen("http://127.0.0.1:18086/?code=C0DE&state=piano", timeout=2); return
            except Exception: time.sleep(0.2)
    threading.Thread(target=user_clicks_allow, daemon=True).start()
    tok = tiktok.login(tmp_path / ".env", port=18086, open_browser=False, http=fake_http, say=lambda *_: None)
    assert tok == "RT-TIK" and "code=C0DE" in seen["body"] and "TIKTOK_REFRESH_TOKEN=RT-TIK" in (tmp_path / ".env").read_text()


def test_registry_uses_the_real_adapter_now(tmp_path):
    from app import config
    from app.publisher import adapters
    s = config.load_settings(); s["paths"] = {**s["paths"], "data_dir": str(tmp_path)}
    s["tiktok"] = {**s.get("tiktok", {}), "mode": "draft"}                  # « web » (par défaut) pilote le navigateur ; « draft » = API officielle
    names = [getattr(a, "platform", "") for a in adapters(s)]
    assert "tiktok" in names
    assert isinstance([a for a in adapters(s) if getattr(a, "platform", "") == "tiktok"][0], tiktok.TikTok)


def test_page_shows_both_platform_connections():
    from app.ui.page import PAGE
    assert "['TikTok',i.tiktok]" in PAGE and "['YouTube',i.youtube]" in PAGE
