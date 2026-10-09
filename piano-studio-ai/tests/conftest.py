import pytest

from app import config


@pytest.fixture(autouse=True)
def _reserve_allowed_in_tests(monkeypatch):
    """En vrai, l'agent ne prend que le dossier MIDI de l'utilisateur (songs.only_mine). Les tests ont besoin des morceaux de la réserve."""
    orig = config.load_settings

    def load(path=None):
        s = orig(path)
        s.setdefault("songs", {})["only_mine"] = False
        return s
    monkeypatch.setattr(config, "load_settings", load)
