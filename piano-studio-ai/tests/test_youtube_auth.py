import os
import threading
import time
import urllib.request
import pytest
from app import config
from app.publisher import youtube_auth as ya


def test_auth_url_asks_for_offline_upload_access():
    u = ya.auth_url("CID", "http://127.0.0.1:8085")
    assert "client_id=CID" in u and "access_type=offline" in u and "youtube.upload" in u and "prompt=consent" in u


def test_exchange_returns_refresh_token_or_explains():
    assert ya.exchange_code("c", "id", "sec", "http://x", post=lambda url, d: {"refresh_token": "R", "access_token": "A"}) == "R"
    with pytest.raises(RuntimeError, match="jeton durable"):
        ya.exchange_code("c", "id", "sec", "http://x", post=lambda url, d: {"access_token": "A"})


def test_env_file_is_updated_in_place_and_protected(tmp_path):
    f = tmp_path / ".env"
    f.write_text("A=1\nYOUTUBE_REFRESH_TOKEN=\nB=2\n")
    ya.write_env(f, {"YOUTUBE_REFRESH_TOKEN": "tok", "NEW": "x"})
    assert f.read_text().splitlines() == ["A=1", "YOUTUBE_REFRESH_TOKEN=tok", "B=2", "NEW=x"]
    assert oct(f.stat().st_mode)[-3:] == "600"


def test_env_loader_does_not_override_and_ignores_comments(tmp_path, monkeypatch):
    f = tmp_path / ".env"
    f.write_text("# c\nPIANO_T1=fromfile\nPIANO_T2=\"quoted\"\nPIANO_T3=\n")
    monkeypatch.setenv("PIANO_T1", "already")
    monkeypatch.delenv("PIANO_T2", raising=False); monkeypatch.delenv("PIANO_T3", raising=False)
    config.load_env(f)
    assert os.environ["PIANO_T1"] == "already" and os.environ["PIANO_T2"] == "quoted" and "PIANO_T3" not in os.environ


def test_full_login_flow_with_simulated_google(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "CID"); monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "SEC")
    seen = {}
    def fake_post(url, d): seen.update(d); return {"refresh_token": "RT123"}
    def user_clicks_allow():
        time.sleep(0.5)
        for _ in range(40):                                   # le navigateur est redirigé vers l'adresse locale avec ?code=...
            try:
                urllib.request.urlopen("http://127.0.0.1:18085/?code=THECODE&state=piano", timeout=2); return
            except Exception: time.sleep(0.2)
    threading.Thread(target=user_clicks_allow, daemon=True).start()
    tok = ya.login(tmp_path / ".env", port=18085, open_browser=False, post=fake_post, say=lambda *_: None)
    assert tok == "RT123" and seen["code"] == "THECODE" and "YOUTUBE_REFRESH_TOKEN=RT123" in (tmp_path / ".env").read_text()


def test_login_explains_missing_credentials(tmp_path, monkeypatch):
    monkeypatch.delenv("YOUTUBE_CLIENT_ID", raising=False); monkeypatch.delenv("YOUTUBE_CLIENT_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="manquent"):
        ya.login(tmp_path / ".env", open_browser=False, say=lambda *_: None)
