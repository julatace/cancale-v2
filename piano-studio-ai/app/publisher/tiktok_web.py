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
BROWSER = "Google Chrome"      # "Safari" ou "Google Chrome" (réglé par --browser)
PROFILE = ""            # profil Chrome à utiliser (dossier, ex. « Profile 2 », ou nom affiché) ; vide = celui de la fenêtre au premier plan
UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload?from=webapp"


def chrome_profiles() -> list[dict]:
    """Profils Chrome du Mac : [{dir, name, email}] (lus dans le fichier « Local State » de Chrome)."""
    f = Path.home() / "Library" / "Application Support" / "Google" / "Chrome" / "Local State"
    try:
        cache = json.loads(f.read_text()).get("profile", {}).get("info_cache", {})
    except Exception:
        return []
    return [{"dir": d, "name": v.get("name", d), "email": v.get("user_name", "")} for d, v in sorted(cache.items())]


def resolve_profile(wanted: str) -> str:
    """Nom affiché, e-mail ou dossier -> dossier du profil. Erreur claire si introuvable."""
    if not wanted:
        return ""
    profs = chrome_profiles()
    for p in profs:
        if wanted.lower() in (p["dir"].lower(), p["name"].lower(), p["email"].lower()):
            return p["dir"]
    if profs:
        raise RuntimeError(f"profil Chrome « {wanted} » introuvable. Profils : " + ", ".join(f"{p['name']} ({p['dir']})" for p in profs))
    return wanted                                           # liste illisible : on tente tel quel


def _osa(script: str, timeout: int = 30) -> str:
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise RuntimeError(r.stderr.strip() or "osascript a échoué")
    return r.stdout.strip()


def _js(code: str) -> str:
    """Exécute du JavaScript dans l'onglet actif du navigateur."""
    esc = code.replace("\\", "\\\\").replace('"', '\\"')
    if BROWSER == "Safari":
        cmd = f'tell application "Safari" to do JavaScript "{esc}" in current tab of front window'
    else:
        cmd = f'tell application "{BROWSER}" to execute active tab of front window javascript "{esc}"'
    try:
        return _osa(cmd)
    except RuntimeError as e:
        if "JavaScript" in str(e) and ("Apple" in str(e) or "AppleScript" in str(e)):
            where = ("Safari > Réglages > Développeur" if BROWSER == "Safari"
                     else "menu Présentation > Développeur > « Autoriser le JavaScript des événements Apple »")
            raise RuntimeError(f"{BROWSER} refuse le JavaScript : active-le ({where}). Message exact : " + str(e)[:300]) from e
        raise


def _keys(*lines: str):
    _osa('tell application "System Events"\n' + "\n".join(lines) + "\nend tell")


def _clip(text: str):
    subprocess.run(["pbcopy"], input=text.encode(), check=True)


def _wait(cond_js: str, what: str, timeout: int = 90) -> None:
    end = time.monotonic() + timeout
    last = ""
    while time.monotonic() < end:
        try:
            if _js(cond_js) == "true":
                return
            last = ""
        except RuntimeError as e:
            last = str(e)
            if "JavaScript" in last or "allow" in last.lower() or "autoris" in last.lower():
                raise                                              # réglage Safari manquant : inutile d'attendre 90 s
        time.sleep(2)
    try:
        info = _js('document.location.href + " | " + document.title + " | fichiers:" + document.querySelectorAll("input[type=file]").length')
    except RuntimeError as e:
        info = f"lecture de la page impossible ({e})"
    raise RuntimeError(f"TikTok : {what} (délai dépassé). Page vue par l'agent : {info}" + (f" ; dernière erreur : {last}" if last else ""))


def split_caption(caption: str) -> tuple[str, list[str]]:
    """Sépare le texte des hashtags de fin ; hashtags nettoyés (ASCII, sans accents), 8 au maximum."""
    import re
    import unicodedata
    tags = re.findall(r"#[\w]+", caption)
    body = re.sub(r"\s*#[\w]+", "", caption).strip()
    clean = []
    for h in tags:
        a = unicodedata.normalize("NFKD", h).encode("ascii", "ignore").decode()
        if len(a) > 1 and a.lower() not in [c.lower() for c in clean]:
            clean.append(a)
    return body, clean[:8]


_FIND_BTN = ("(function(){var re=/(s[ée]lectionner|select|choisir|choose|importer|upload)/i,best=null,ba=1e12;"
             "document.querySelectorAll('button,[role=button],label,a,div,span').forEach(function(e){"
             "var t=(e.innerText||'').trim();if(!t||t.length>40||!re.test(t))return;var r=e.getBoundingClientRect();"
             "if(r.width<60||r.height<24||r.top<0||r.bottom>window.innerHeight||r.left<0)return;var a=r.width*r.height;if(a<ba){ba=a;best=r}});"
             "if(!best){var el=document.querySelector('input[type=file]');if(!el)return '';"
             "for(var k=0;k<6&&el.parentElement;k++){el=el.parentElement;var q=el.getBoundingClientRect();if(q.width>120&&q.height>40)break;}best=el.getBoundingClientRect()}"
             "return Math.round(window.screenX+best.left+best.width/2)+','+Math.round(window.screenY+(window.outerHeight-window.innerHeight)+best.top+best.height/2);})()")


def _sheet_open() -> bool:
    """La fenêtre « Ouvrir » de macOS est-elle ouverte sur le navigateur ?"""
    try:
        return _osa(f'tell application "System Events" to tell process "{BROWSER}" to return (exists sheet 1 of window 1) or (exists window "Ouvrir") or (exists window "Open")') == "true"
    except RuntimeError:
        return False


def _real_click_upload(say) -> None:
    """Vrai clic souris sur le bouton « Sélectionner … » (un clic JavaScript est refusé : pas de geste humain). Ne continue que si la fenêtre « Ouvrir » apparaît."""
    import shutil
    if not shutil.which("cliclick"):
        raise RuntimeError("cliclick manquant : lance  brew install cliclick")
    _js('window.scrollTo(0,0); "ok"')
    for attempt in (1, 2):
        pos = _js(_FIND_BTN)
        if not pos:
            raise RuntimeError("bouton d'envoi de fichier introuvable sur la page")
        x, y = (int(float(v)) for v in pos.split(","))
        say(f"🖱 Clic sur le bouton d'envoi ({x},{y})")
        subprocess.run(["cliclick", f"m:{x},{y}", "w:300", f"c:{x},{y}"], check=True)
        for _ in range(12):                                   # jusqu'à 6 s pour voir la fenêtre « Ouvrir »
            time.sleep(0.5)
            if _sheet_open():
                return
    raise RuntimeError("la fenêtre « Ouvrir » de macOS ne s'est pas ouverte après le clic (rien n'a été tapé). "
                       "Vérifie que Terminal a l'accès Accessibilité et que la fenêtre Chrome n'est pas cachée derrière une autre")


def _shot(name="tiktok_web_erreur.png"):
    try:
        out = Path(__file__).resolve().parents[2] / "data" / "debug" / name
        out.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["screencapture", "-x", str(out)], timeout=10)
        return str(out)
    except Exception:
        return ""


def post(video: Path, caption: str, publish: bool = False, say=log.info) -> str:
    try:
        return _post(video, caption, publish, say)
    except Exception as e:
        shot = _shot()
        raise RuntimeError(f"{e}" + (f" (capture d'écran : {shot})" if shot else "")) from e


def open_url(url: str, say, label: str) -> None:
    """Ouvre `url` dans le navigateur choisi (et le bon profil Chrome) après avoir vérifié le réglage JavaScript."""
    say(f"🔐 Test du réglage JavaScript de {BROWSER}…")
    _osa(f'tell application "{BROWSER}" to activate')
    _js("1+1")
    say(f"🌐 Ouverture de {label} dans {BROWSER}…")
    if BROWSER == "Safari":
        _osa(f'tell application "Safari"\nactivate\nif (count of windows) = 0 then make new document\n'
             f'set URL of current tab of front window to "{url}"\nend tell')
    elif PROFILE:                                            # ouvre la page DANS le bon profil : sa fenêtre passe au premier plan
        d = resolve_profile(PROFILE)
        say(f"👤 Profil Chrome utilisé : {d}")
        subprocess.run(["open", "-a", BROWSER, "--args", f"--profile-directory={d}", url], check=True)
        time.sleep(3)
        _osa(f'tell application "{BROWSER}" to activate')
    else:
        _osa(f'tell application "{BROWSER}"\nactivate\nif (count of windows) = 0 then make new window\n'
             f'set URL of active tab of front window to "{url}"\nend tell')


def choose_file(path, say) -> None:
    """Vrai clic sur la zone d'envoi, puis dans la fenêtre « Ouvrir » de macOS : Aller au dossier (⇧⌘G) -> chemin collé -> Entrée."""
    say("📁 Sélection du fichier…")
    _real_click_upload(say)
    time.sleep(0.8)
    _clip(str(path))
    _keys('keystroke "g" using {command down, shift down}', "delay 1", 'keystroke "v" using command down', "delay 1",
          "key code 36", "delay 1.5", "key code 36")


def _post(video, caption, publish, say):
    video = Path(video).resolve()
    if not video.exists():
        raise RuntimeError(f"vidéo introuvable : {video}")
    open_url(UPLOAD_URL, say, "TikTok Studio")
    _wait('String(!!document.querySelector("input[type=file]"))', "page d'envoi non chargée")
    if _js('String(/connecter|log in|se connecter/i.test(document.body.innerText.slice(0,400)) && !document.querySelector("input[type=file]"))') == "true":
        raise RuntimeError("TikTok demande de se connecter : connecte ton compte dans Safari puis relance")
    choose_file(video, say)
    say("⏫ Envoi de la vidéo vers TikTok…")
    _wait('String(!!document.querySelector("[contenteditable=true]"))', "la vidéo n'a pas fini de charger", 180)
    time.sleep(3)
    say("✍️ Légende et hashtags…")
    _js('var e=document.querySelector("[contenteditable=true]"); e.focus(); document.execCommand("selectAll"); "ok"')
    body, tags = split_caption(caption)
    _clip(body)
    _keys('keystroke "v" using command down')
    time.sleep(1)
    for tag in tags:                                   # chaque hashtag est TAPÉ puis validé par un espace : TikTok le transforme en vrai hashtag
        _keys('keystroke " "', f'keystroke "{tag}"', "delay 1.2", 'keystroke " "', "delay 0.4")
    _keys("delay 0.5", "key code 53")                  # Échap : ferme la liste de suggestions encore ouverte
    time.sleep(1.5)
    if not publish:
        say("✋ Tout est prêt dans le navigateur : vérifie puis clique sur « Publier » toi-même.")
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

    def __init__(self, publish: bool = False, profile: str = ""):
        self.go, self.profile = publish, profile

    def check(self):
        import shutil
        return (shutil.which("osascript") is not None, "pilote Safari (mode web, sans clé API)")

    def publish(self, video, meta, key):
        cap = (meta.get("tiktok_caption") or meta.get("description") or meta.get("title") or "").strip()
        global PROFILE
        PROFILE = self.profile
        try:
            st = post(video, cap, self.go)
        except Exception as e:
            return Result(self.platform, "FAILED", "", f"{e}")
        return Result(self.platform, "PUBLISHED" if self.go else "EXPORTED", key, st)
