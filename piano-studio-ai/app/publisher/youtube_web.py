"""Publication YouTube en pilotant YouTube Studio dans Chrome (compte déjà connecté) : aucun projet Google Cloud, aucune clé API.

Mêmes prérequis que TikTok (voir tiktok_web.py) : Chrome > Affichage > Développeur > « Autoriser JavaScript dans Apple Events »,
cliclick, Accessibilité pour Terminal. Avantage sur l'API : la vidéo est publiée tout de suite en public (pas de « privé tant que Google
n'a pas validé ton projet »). NON testé sur un vrai YouTube : Studio change souvent ; chaque étape dit ce qui bloque.
La miniature personnalisée n'est pas envoyée (à ajouter à la main dans Studio si tu y tiens)."""
import logging
import time
from pathlib import Path

from . import tiktok_web as tw
from .base import Result

log = logging.getLogger("piano.youtube_web")
UPLOAD_URL = "https://www.youtube.com/upload"


def _click(selector: str) -> bool:
    return tw._js(f'var e=document.querySelector({selector!r}); if(e){{e.click();"true"}}else{{"false"}}') == "true"


def _paste_into(selector: str, text: str) -> None:
    ok = tw._js(f'var e=document.querySelector({selector!r}); if(e){{e.focus(); document.execCommand("selectAll"); "true"}}else{{"false"}}')
    if ok != "true":
        raise RuntimeError(f"zone de texte YouTube introuvable ({selector})")
    tw._clip(text)
    tw._keys('keystroke "v" using command down')
    time.sleep(0.8)


def post(video: Path, title: str, description: str, publish: bool = False, say=log.info) -> str:
    try:
        return _post(video, title, description, publish, say)
    except Exception as e:
        shot = tw._shot("youtube_web_erreur.png")
        raise RuntimeError(f"{e}" + (f" (capture d'écran : {shot})" if shot else "")) from e


def _post(video, title, description, publish, say) -> str:
    video = Path(video).resolve()
    if not video.exists():
        raise RuntimeError(f"vidéo introuvable : {video}")
    tw.open_url(UPLOAD_URL, say, "YouTube Studio")
    tw._wait('String(!!document.querySelector("input[type=file]"))', "fenêtre d'envoi de YouTube non chargée", 60)
    if tw._js('String(location.hostname.indexOf("accounts.google")>=0)') == "true":
        raise RuntimeError("YouTube demande de se connecter : connecte ta chaîne dans ce profil Chrome puis relance")
    tw.choose_file(video, say)
    say("⏫ Envoi de la vidéo vers YouTube…")
    tw._wait('String(!!document.querySelector("#title-textarea #textbox"))', "le formulaire de la vidéo n'apparaît pas", 180)
    time.sleep(2)
    say("✍️ Titre et description…")
    _paste_into("#title-textarea #textbox", title[:100])
    _paste_into("#description-textarea #textbox", description[:4900])
    say("👶 « Pas conçue pour les enfants »…")
    if not _click('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]'):
        raise RuntimeError("choix « pas conçue pour les enfants » introuvable")
    for step in ("Détails", "Éléments de la vidéo", "Vérifications"):          # Suivant ×3 jusqu'à la visibilité
        time.sleep(1.5)
        if not _click("#next-button"):
            raise RuntimeError(f"bouton « Suivant » introuvable (étape {step})")
    time.sleep(1.5)
    if not _click('tp-yt-paper-radio-button[name="PUBLIC"]'):
        raise RuntimeError("choix « Public » introuvable")
    if not publish:
        say("✋ Tout est prêt dans YouTube Studio : vérifie puis clique sur « Publier » toi-même.")
        return "prêt (non publié)"
    say("🚀 Clic sur « Publier »…")
    time.sleep(1)
    tw._wait('String(!!document.querySelector("#done-button:not([disabled])") && document.querySelector("#done-button").getAttribute("aria-disabled")!=="true")',
             "le bouton « Publier » reste grisé (la vidéo est encore en cours d'envoi)", 300)
    _click("#done-button")
    time.sleep(5)
    link = tw._js('var a=document.querySelector("ytcp-video-share-dialog a, .video-url-fadeable a, a[href*=\\"youtu.be\\"]"); a?a.href:""')
    return link or "publié"


class YouTubeWeb:
    platform = "youtube"

    def __init__(self, publish: bool = False, profile: str = ""):
        self.go, self.profile = publish, profile

    def check(self):
        import shutil
        return (shutil.which("osascript") is not None, "pilote YouTube Studio dans Chrome (mode web, sans clé API)")

    def publish(self, video, meta, key):
        from .youtube import YouTube
        sn = YouTube.build_snippet({**meta, "title": meta.get("youtube_title") or meta.get("title") or "Piano"}, "public", "10")["snippet"]
        tw.PROFILE = self.profile
        try:
            st = post(video, sn["title"], sn["description"], self.go)
        except Exception as e:
            return Result(self.platform, "FAILED", "", f"{e}")
        return Result(self.platform, "PUBLISHED" if self.go else "EXPORTED", key, st)
