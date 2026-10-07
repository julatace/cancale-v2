"""Publication TikTok en pilotant Safari (déjà connecté au compte), sans API.

Safari doit avoir : Développement > « Autoriser JavaScript provenant d'Apple Events » (menu Développement :
Safari > Réglages > Avancées > « Afficher les fonctionnalités pour les développeurs web »), et l'app Terminal
doit avoir l'accès Accessibilité. Le texte passe par le presse-papiers (aucun caractère tapé à la main).
NON testé sur un vrai TikTok : l'interface web de TikTok change ; chaque étape dit ce qui bloque.
"""
import json
import logging
import subprocess
import time
from pathlib import Path

from .base import Result

log = logging.getLogger("piano.tiktok_web")
UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload?from=webapp"


def _osa(script: str, timeout: int = 30) -> str:
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError(r.stderr.strip() or "osascript a échoué")
    return r.stdout.strip()


def _js(code: str) -> str:
    """Exécute du JavaScript dans l'onglet actif de Safari."""
    esc = code.replace("\\", "\\\\").replace('"', '\\"')
    try:
        return _osa(f'tell application "Safari" to do JavaScript "{esc}" in current tab of front window')
    except RuntimeError as e:
        if "JavaScript" in str(e) and "Apple" in str(e):
            raise RuntimeError("Safari refuse le JavaScript : active « Autoriser JavaScript provenant d'Apple Events » "
                               "(menu Développement de Safari)") from e
        raise


def _keys(*lines: str):
    _osa('tell application "System Events"\n' + "\n".join(lines) + "\nend tell")


def _clip(text: str):
    subprocess.run(["pbcopy"], input=text.encode(), check=True)


def _wait(cond_js: str, what: str, timeout: int = 90) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            if _js(cond_js) == "true":
                return
        except RuntimeError:
            pass
        time.sleep(2)
    raise RuntimeError(f"TikTok : {what} (délai dépassé) — vérifie que tu es connecté dans Safari")


def post(video: Path, caption: str, publish: bool = False, say=log.info) -> str:
    video = Path(video).resolve()
    if not video.exists():
        raise RuntimeError(f"vidéo introuvable : {video}")
    say("🌐 Ouverture de TikTok Studio dans Safari…")
    _osa(f'tell application "Safari"\nactivate\nif (count of windows) = 0 then make new document\n'
         f'set URL of current tab of front window to "{UPLOAD_URL}"\nend tell')
    _wait('String(!!document.querySelector("input[type=file]"))', "page d'envoi non chargée")
    if _js('String(/connecter|log in|se connecter/i.test(document.body.innerText.slice(0,400)) && !document.querySelector("input[type=file]"))') == "true":
        raise RuntimeError("TikTok demande de se connecter : connecte ton compte dans Safari puis relance")
    say("📁 Sélection de la vidéo…")
    _js('document.querySelector("input[type=file]").click(); "ok"')
    time.sleep(2.5)
    _clip(str(video))
    _keys('keystroke "g" using {command down, shift down}', "delay 1", 'keystroke "v" using command down', "delay 1",
          "key code 36", "delay 1.5", "key code 36")                    # Aller au dossier → coller le chemin → Entrée → Ouvrir
    say("⏫ Envoi de la vidéo vers TikTok…")
    _wait('String(!!document.querySelector("[contenteditable=true]"))', "la vidéo n'a pas fini de charger", 180)
    time.sleep(3)
    say("✍️ Légende et hashtags…")
    _js('var e=document.querySelector("[contenteditable=true]"); e.focus(); document.execCommand("selectAll"); "ok"')
    _clip(caption)
    _keys('keystroke "v" using command down')
    time.sleep(2)
    if not publish:
        say("✋ Tout est prêt dans Safari : vérifie puis clique sur « Publier » toi-même.")
        return "prêt (non publié)"
    say("🚀 Clic sur « Publier »…")
    ok = _js('var b=[...document.querySelectorAll("button")].find(x=>/^(publier|post)$/i.test(x.innerText.trim())&&!x.disabled);'
             'if(b){b.click();"true"}else{"false"}')
    if ok != "true":
        raise RuntimeError("bouton « Publier » introuvable ou grisé (vidéo encore en traitement ?)")
    time.sleep(6)
    _js('var b=[...document.querySelectorAll("button")].find(x=>/^(publier maintenant|post now)$/i.test(x.innerText.trim())); if(b)b.click(); "ok"')
    return "publié"


class TikTokWeb:
    platform = "tiktok"

    def __init__(self, publish: bool = False):
        self.go = publish

    def check(self):
        import shutil
        return (shutil.which("osascript") is not None, "pilote Safari (mode web, sans clé API)")

    def publish(self, video, meta, key):
        cap = (meta.get("tiktok_caption") or meta.get("description") or meta.get("title") or "").strip()
        try:
            st = post(video, cap, self.go)
        except Exception as e:
            return Result(self.platform, "FAILED", "", f"{e}")
        return Result(self.platform, "PUBLISHED" if self.go else "EXPORTED", key, st)
