import yaml

from app import config
from .base import Outbox, Unavailable
from .youtube import YouTube
from .tiktok import TikTok
from .tiktok_web import TikTokWeb


def adapters(settings, platforms_cfg=None, fmt=None):
    cfg = platforms_cfg or yaml.safe_load(open(config.ROOT / "config" / "platforms.yaml"))
    out = [Outbox(config.resolve(settings, "data_dir") / "published")]
    yt = settings.get("youtube", {})
    reg = {"youtube": YouTube(privacy=yt.get("privacy", "public"), category=str(yt.get("category", "10"))),
           "tiktok": (TikTokWeb(publish=bool(settings.get("tiktok", {}).get("web_publish", False))) if settings.get("tiktok", {}).get("mode") == "web"
              else TikTok(mode=settings.get("tiktok", {}).get("mode", "draft"))),
           "instagram": Unavailable("instagram", "un compte Business + Meta app approuvée"),
           "facebook": Unavailable("facebook", "une Page + Meta app approuvée")}
    out += [reg[k] for k, v in cfg.items() if v.get("enabled") and k in reg and (fmt is None or fmt in v.get("formats", [fmt]))]
    return out
