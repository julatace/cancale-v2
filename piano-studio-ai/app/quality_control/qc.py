import json
import re
import subprocess
from pathlib import Path


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def check(path, expect_w=1080, expect_h=1920, dur_range=(5, 60)) -> dict:
    p, issues, score = Path(path), [], 100
    if not p.exists() or p.stat().st_size < 50_000:
        return {"score": 0, "issues": ["fichier absent ou trop petit"]}
    pr = _run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height:format=duration",
               "-of", "json", str(p)])
    try:
        info = json.loads(pr.stdout)
    except json.JSONDecodeError:
        return {"score": 0, "issues": ["fichier illisible"]}
    st = info.get("streams", [])
    v = next((s for s in st if s["codec_type"] == "video"), None)
    dur = float(info.get("format", {}).get("duration", 0))
    if not v: return {"score": 0, "issues": ["pas de piste vidéo"]}
    if (v["width"], v["height"]) != (expect_w, expect_h): issues.append("mauvaise résolution"); score -= 30
    if not any(s["codec_type"] == "audio" for s in st): issues.append("pas d'audio"); score -= 40
    if not dur_range[0] <= dur <= dur_range[1]: issues.append(f"durée {dur:.1f}s hors plage"); score -= 20
    r = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(p), "-vf", "blackdetect=d=1:pic_th=0.98,freezedetect=n=-60dB:d=4",
              "-af", "volumedetect", "-f", "null", "-"]).stderr
    if "black_start" in r: issues.append("écran noir"); score -= 30
    if "freeze_start" in r: issues.append("image figée"); score -= 25
    m = re.search(r"mean_volume: (-?[\d.]+) dB", r)
    if m and float(m.group(1)) < -35: issues.append("audio trop faible"); score -= 30
    return {"score": max(score, 0), "issues": issues, "duration": dur}


def verdict(score: float, publish_min=90, autofix_min=80) -> str:
    return "PUBLISH" if score >= publish_min else "AUTOFIX" if score >= autofix_min else "REJECT"
