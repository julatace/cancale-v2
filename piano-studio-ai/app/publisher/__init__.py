import yaml

from app import config
from .base import Outbox, Unavailable
from .youtube import YouTube
from .tiktok import TikTok


def adapters(settings, platforms_cfg=None):
    cfg = platforms_cfg or yaml.safe_load(open(config.ROOT / "config" / "platforms.yaml"))
    out = [Outbox(config.resolve(settings, "data_dir") / "published")]
    reg = {"youtube": YouTube(),
           "tiktok": TikTok(mode=settings.get("tiktok", {}).get("mode", "draft")),
           "instagram": Unavailable("instagram", "un compte Business + Meta app approuvée"),
           "facebook": Unavailable("facebook", "une Page + Meta app approuvée")}
    out += [reg[k] for k, v in cfg.items() if v.get("enabled") and k in reg]
    return out
