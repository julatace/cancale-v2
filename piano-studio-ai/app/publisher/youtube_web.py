"""Publication YouTube en pilotant YouTube Studio dans Chrome (compte déjà connecté) : aucun projet Google Cloud, aucune clé API.

Mêmes prérequis que TikTok (voir tiktok_web.py) : Chrome > Affichage > Développeur > « Autoriser JavaScript dans Apple Events »,
cliclick, Accessibilité pour Terminal. Avantage sur l'API : la vidéo est publiée tout de suite en public (pas de « privé tant que Google
n'a pas validé ton projet »). NON testé sur un vrai YouTube : Studio change souvent ; chaque étape dit ce qui bloque.
La miniature personnalisée n'est pas envoyée (à ajouter à la main dans Studio si tu y tiens)."""
import json
import logging
import re
import time
from pathlib import Path

from . import tiktok_web as tw
from .base import Result

log = logging.getLogger("piano.youtube_web")
UPLOAD_URL = "https://www.youtube.com/upload"


def _click(selector: str) -> bool:
    return tw._js(f'var e=document.querySelector({selector!r}); if(e){{e.click();"true"}}else{{"false"}}') == "true"


def _insert_js(selector: str, text: str) -> str:
    """JavaScript qui remplace le contenu de la zone de texte par `text`, comme une vraie saisie (événements « input » compris), puis rend le texte lu."""
    import json
    return ("(function(){var e=document.querySelector(" + json.dumps(selector) + ");if(!e)return 'absent';e.focus();"
            "document.execCommand('selectAll');document.execCommand('delete');var L=" + json.dumps(text) + ".split('\\n');"
            "for(var i=0;i<L.length;i++){if(i>0)document.execCommand('insertLineBreak');if(L[i])document.execCommand('insertText',false,L[i]);}"
            "e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));return e.innerText||e.textContent||'';})()")


def _same(a: str, b: str) -> bool:
    norm = lambda s: " ".join((s or "").split())
    return norm(a)[:60] == norm(b)[:60] and len(norm(a)) >= min(len(norm(b)), 20)


def _read(selector: str) -> str:
    return tw._js(f'var e=document.querySelector({selector!r}); e?(e.innerText||e.textContent||""):""')


def _paste_into(selector: str, text: str) -> None:
    """Écrit le texte dans la zone de YouTube. YouTube remet parfois le nom du fichier juste après : on réécrit puis on RELIT après un délai,
    jusqu'à ce que le texte tienne (5 essais), et en dernier recours avec le presse-papiers."""
    for attempt in range(5):
        got = tw._js(_insert_js(selector, text))
        if got == "absent":
            time.sleep(1.5)
            continue
        time.sleep(1.6)                                              # laisse YouTube finir de « s'installer » avant de vérifier
        if _same(_read(selector), text):
            return
        log.warning("texte écrasé par YouTube (%s…), nouvel essai %d/5", (_read(selector) or "")[:30], attempt + 1)
    ok = tw._js(f'var e=document.querySelector({selector!r}); if(e){{e.focus(); document.execCommand("selectAll"); "true"}}else{{"false"}}')
    if ok != "true":
        raise RuntimeError(f"zone de texte YouTube introuvable ({selector})")
    tw._clip(text)
    tw._keys('keystroke "v" using command down')
    time.sleep(1.2)
    got = _read(selector)
    if not _same(got, text):
        raise RuntimeError(f"le texte n'a pas été écrit dans YouTube ({selector}) : « {(got or '')[:40]} »")


def _wait_progress(cond_js: str, what: str, timeout: int, say) -> None:
    """Comme tw._wait, mais en racontant l'avancement de l'envoi toutes les 30 s."""
    end = time.monotonic() + timeout
    last = 0.0
    while time.monotonic() < end:
        try:
            if tw._js(cond_js) == "true":
                return
        except RuntimeError:
            pass
        if time.monotonic() - last > 30:
            last = time.monotonic()
            prog = tw._js('var p=document.querySelector("ytcp-video-upload-progress");(p?p.innerText:"").replace(/\\s+/g," ").slice(0,90)')
            if prog:
                say(f"   YouTube : {prog}")
        time.sleep(3)
    raise RuntimeError(f"{what} (délai dépassé)")


def _visibility(publish_at, say) -> None:
    """Dernière étape de YouTube Studio : toujours « Public » ; avec une date, « Programmer » (YouTube met la vidéo en ligne lui-même à l'heure choisie)."""
    if not _click('tp-yt-paper-radio-button[name="PUBLIC"]'):
        raise RuntimeError("choix « Public » introuvable")
    time.sleep(0.6)
    if tw._js('var r=document.querySelector(\'tp-yt-paper-radio-button[name="PUBLIC"]\');r?String(r.getAttribute("aria-checked")==="true"||r.hasAttribute("checked")):"false"') != "true":
        raise RuntimeError("la vidéo est restée privée : le choix « Public » n'a pas été pris en compte")
    if not publish_at:
        return
    from datetime import datetime
    when = datetime.fromisoformat(publish_at)
    say(f"🗓 Programmation sur YouTube : {when:%d/%m/%Y %H:%M}…")
    if not _click("#second-container-expand-button"):
        raise RuntimeError("section « Programmer » introuvable dans YouTube Studio")
    tw._wait('String(!!document.querySelector("#datepicker-trigger"))', "le sélecteur de date de YouTube n'apparaît pas", 15)
    _click("#datepicker-trigger")
    tw._wait('String(!!document.querySelector("ytcp-date-picker input, tp-yt-paper-dialog input"))', "le champ date de YouTube n'apparaît pas", 15)
    lang = "navigator.language"
    date_js = f"new Date({when.year},{when.month - 1},{when.day}).toLocaleDateString({lang},{{day:'numeric',month:'short',year:'numeric'}})"
    time_js = f"new Date({when.year},{when.month - 1},{when.day},{when.hour},{when.minute}).toLocaleTimeString({lang},{{hour:'numeric',minute:'2-digit'}})"
    for sel, expr in (("ytcp-date-picker input, tp-yt-paper-dialog input", date_js), ("#time-of-day-container input", time_js)):
        got = tw._js(f"(function(){{var e=document.querySelector({json.dumps(sel)});if(!e)return 'absent';e.focus();document.execCommand('selectAll');"
                     f"document.execCommand('insertText',false,{expr});return e.value}})()")
        if got == "absent":
            raise RuntimeError(f"champ de programmation YouTube introuvable ({sel})")
        tw._keys("key code 36", "delay 0.5")                                      # Entrée : valide la date / l'heure saisie
        time.sleep(0.6)
        if sel.startswith("#time"):
            tw._js(f"(function(){{var e=document.querySelector({json.dumps(sel)});e&&e.click();return 'ok'}})()")
    time.sleep(0.6)
    shown = tw._js('(function(){var d=document.querySelector("#datepicker-trigger"),t=document.querySelector("#time-of-day-container input");'
                   'return (d?d.innerText:"")+" | "+(t?t.value:"")})()')
    day_ok = str(when.day) in re.findall(r"\d+", shown.split("|")[0])
    min_ok = f"{when.minute:02d}" in shown.split("|")[-1]
    if not (day_ok and min_ok):
        raise RuntimeError(f"la programmation n'a pas été prise en compte par YouTube (affiché : {shown.strip()[:60]})")


def _save_draft(say) -> bool:
    """Ferme la fenêtre d'envoi : YouTube garde la vidéo en BROUILLON (YouTube Studio > Contenu), titre et description compris."""
    say("📝 Programmation impossible : la vidéo reste en brouillon dans YouTube Studio…")
    if tw._js('var b=document.querySelector("ytcp-uploads-dialog #close-button button, ytcp-uploads-dialog #close-button, #close-button");if(b){b.click();"true"}else{"false"}') != "true":
        return False
    time.sleep(2)
    tw._js(tw._click_text_js(r"^(fermer|close|enregistrer|save|oui|yes)$"))
    time.sleep(1.5)
    return True


def post(video: Path, title: str, description: str, publish: bool = False, say=log.info, publish_at: str | None = None) -> str:
    try:
        return _post(video, title, description, publish, say, publish_at)
    except Exception as e:
        shot = tw._shot("youtube_web_erreur.png")
        dump = tw.save_dump("youtube_web")
        raise RuntimeError(f"{e}" + (f" (capture d'écran : {shot})" if shot else "") + (f" (page : {dump})" if dump else "")) from e


UPLOAD_STARTED = False          # vrai dès que la vidéo est envoyée à YouTube : à partir de là, un échec ne doit JAMAIS déclencher un nouvel envoi automatique


def _post(video, title, description, publish, say, publish_at=None) -> str:
    global UPLOAD_STARTED
    UPLOAD_STARTED = False
    video = Path(video).resolve()
    if not video.exists():
        raise RuntimeError(f"vidéo introuvable : {video}")
    tw.open_url(UPLOAD_URL, say, "YouTube Studio", site="youtube")
    tw._wait('String(!!document.querySelector("input[type=file]"))', "fenêtre d'envoi de YouTube non chargée", 60)
    if tw._js('String(location.hostname.indexOf("accounts.google")>=0)') == "true":
        raise RuntimeError("YouTube demande de se connecter : connecte ta chaîne dans ce profil Chrome puis relance")
    tw.choose_file(video, say, verify='String(!!document.querySelector("#title-textarea #textbox"))')
    UPLOAD_STARTED = True
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
    tw.trace("youtube", "1_texte")
    try:
        _visibility(publish_at, say)
    except RuntimeError as e:
        tw.trace("youtube", "2_visibilite_echec")
        if publish_at and _save_draft(say):                                        # la programmation n'a pas pris : brouillon, rien n'est perdu ni publié par erreur
            return f"brouillon YouTube (programmation impossible : {str(e)[:120]})"
        raise
    tw.trace("youtube", "2_visibilite")
    if not publish:
        say("✋ Tout est prêt dans YouTube Studio : vérifie puis clique sur « Publier » toi-même.")
        return "prêt (non publié)"
    say("🚀 Clic sur « Publier »…")
    time.sleep(1)
    budget = int(min(2400, 240 + video.stat().st_size / 1e6 * 60))             # connexion lente : l'envoi peut durer plusieurs minutes (YouTube ne finalise qu'à la fin)
    say(f"⏳ Attente de la fin de l'envoi vers YouTube (jusqu'à {budget // 60} min)…")
    _wait_progress('String(!!document.querySelector("#done-button:not([disabled])") && document.querySelector("#done-button").getAttribute("aria-disabled")!=="true")',
                   "le bouton « Publier » de YouTube reste grisé (l'envoi n'est pas terminé)", budget, say)
    _click("#done-button")
    end = time.monotonic() + budget                                          # YouTube doit CONFIRMER (fenêtre « Vidéo publiée / programmée »)
    done = False
    last = 0.0
    while time.monotonic() < end:
        if time.monotonic() - last > 30:
            last = time.monotonic()
            prog = tw._js('var p=document.querySelector("ytcp-video-upload-progress");(p?p.innerText:"").replace(/\\s+/g," ").slice(0,90)')
            if prog:
                say(f"   YouTube : {prog}")
        if tw._js('String(!!document.querySelector("ytcp-video-share-dialog, #share-url, .video-url-fadeable") || !document.querySelector("ytcp-uploads-dialog"))') == "true":
            done = True
            break
        time.sleep(2)
    tw.trace("youtube", "3_apres_publication")
    if not done:
        raise RuntimeError("YouTube n'a pas confirmé la publication (la fenêtre d'envoi est restée ouverte)")
    link = tw._js('var a=document.querySelector("ytcp-video-share-dialog a, .video-url-fadeable a, a[href*=\\"youtu.be\\"]"); a?a.href:""')
    tw._js('var b=document.querySelector("ytcp-video-share-dialog #close-button button, ytcp-video-share-dialog #close-button, #close-button button");if(b)b.click();"ok"')   # ferme la fenêtre : on reste sur la même page
    if publish_at:
        from datetime import datetime
        return f"programmée le {datetime.fromisoformat(publish_at):%d/%m/%Y à %H:%M}" + (f" · {link}" if link else "")
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
        pa = meta.get("publish_at")
        try:
            st = post(video, sn["title"], sn["description"], self.go or bool(pa), publish_at=pa)
        except Exception as e:
            if UPLOAD_STARTED:                                    # la vidéo est peut-être déjà dans YouTube Studio (brouillon) : pas de renvoi automatique
                return Result(self.platform, "UNCERTAIN", "", f"{e} — interrompu après l'envoi : regarde YouTube Studio > Contenu avant de réessayer")
            return Result(self.platform, "FAILED", "", f"{e}")
        if st.startswith("brouillon"):
            return Result(self.platform, "DRAFT", key, st)
        return Result(self.platform, "SCHEDULED" if pa else ("PUBLISHED" if self.go else "EXPORTED"), key, st)
