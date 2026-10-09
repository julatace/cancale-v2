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


@pytest.fixture(autouse=True)
def _isolated_last_batch(monkeypatch, tmp_path_factory):
    """La trace de la « dernière fabrication » ne doit jamais fuiter entre les tests (ni toucher aux vrais fichiers)."""
    from app.scheduler import queue
    monkeypatch.setattr(queue, "BATCH_FILE", tmp_path_factory.mktemp("batch") / "last_batch.json")
