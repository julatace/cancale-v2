import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Result:
    platform: str
    status: str          # PUBLISHED | NOT_CONFIGURED | FAILED | EXPORTED
    post_id: str = ""
    detail: str = ""


class NotConfigured(Exception):
    pass


def env(name: str) -> str:
    v = os.environ.get(name, "")
    if not v:
        raise NotConfigured(name)
    return v


class Outbox:
    """Toujours disponible : dépose vidéo + métadonnées prêtes à poster (filet de sécurité)."""
    platform = "outbox"

    def __init__(self, root): self.root = Path(root)

    def publish(self, video: Path, meta: dict, key: str) -> Result:
        d = self.root / key
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy2(video, d / "video.mp4")
        (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
        return Result(self.platform, "EXPORTED", key, str(d))


class Unavailable:
    """TikTok / Instagram / Facebook : l'API officielle exige une app approuvée par la plateforme."""
    def __init__(self, platform, needs): self.platform, self.needs = platform, needs

    def publish(self, video, meta, key) -> Result:
        return Result(self.platform, "NOT_CONFIGURED", detail=f"nécessite {self.needs}")
