"""Publication TikTok en pilotant Safari (déjà connecté au compte), sans API.

Safari doit avoir : Développement > « Autoriser JavaScript provenant d'Apple Events » (menu Développement :
Safari > Réglages > Avancées > « Afficher les fonctionnalités pour les développeurs web »), et l'app Terminal
doit avoir l'accès Accessibilité. Le texte passe par le presse-papiers (aucun caractère tapé à la main).
NON testé sur un vrai TikTok : l'interface web de TikTok change ; chaque étape dit ce qui bloque.
"""
import json
import logging
import re
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


TARGET = "active tab of front window"        # onglet visé par le JavaScript : « tab id T of window id W » une fois l'onglet du site ouvert
TABS: dict[str, str] = {}                      # un onglet par site (tiktok, youtube), gardé et réutilisé pour toutes les vidéos


def _js(code: str) -> str:
    """Exécute du JavaScript dans l'onglet visé du navigateur."""
    esc = code.replace("\\", "\\\\").replace('"', '\\"')
    if BROWSER == "Safari":
        cmd = f'tell application "Safari" to do JavaScript "{esc}" in current tab of front window'
    else:
        cmd = f'tell application "{BROWSER}" to execute {TARGET} javascript "{esc}"'
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



def _click_text_js(pattern: str, scope: str = "document") -> str:
    """JavaScript : clique sur le plus petit élément visible dont le texte correspond à `pattern` (regex) ; rend « true » / « false »."""
    return ("(function(){var re=new RegExp(" + json.dumps(pattern) + ",'i'),best=null,ba=1e12;" + scope + ".querySelectorAll('button,label,[role=radio],[role=button],[role=option],li,div,span,input[type=radio]').forEach(function(e){"
            "var t=((e.innerText||e.value||e.getAttribute('aria-label')||'')+'').trim();if(!t||t.length>40||!re.test(t))return;var r=e.getBoundingClientRect();"
            "if(!(r.width>0&&r.height>0)||e.disabled||e.getAttribute('aria-disabled')==='true'||/disabled/i.test(e.className||''))return;var a=r.width*r.height;if(a<ba){ba=a;best=e}});"
            "if(!best)return 'false';best.click();return 'true'})()")


def _tt_fields() -> list[dict]:
    """Champs date / heure de la zone « Quand publier » de TikTok Studio (repérés par la forme de leur valeur)."""
    raw = _js("(function(){var o=[];document.querySelectorAll('input').forEach(function(e,i){var r=e.getBoundingClientRect();if(!(r.width>0&&r.height>0))return;"
              "o.push(i+'|'+(e.value||'')+'|'+(e.placeholder||''))});return o.join('\\n')})()")
    out = []
    for line in (raw or "").splitlines():
        i, v, ph = (line.split("|") + ["", ""])[:3]
        kind = "time" if re.fullmatch(r"\s*\d{1,2}:\d{2}(\s*[AaPp][Mm])?\s*", v) else "date" if re.search(r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|\d{1,2}\s+\w+\.?\s+\d{4}", v) else ""
        if kind:
            out.append({"i": int(i), "kind": kind, "value": v})
    return out


def _open_field(i: int) -> None:
    _js(f"(function(){{var e=document.querySelectorAll('input')[{i}];e.focus();e.click();return 'ok'}})()")
    time.sleep(0.8)


def _pick_text(text: str) -> bool:
    """Clique dans la fenêtre déroulante ouverte l'élément dont le texte est exactement `text` (jour du calendrier, heure, minutes)."""
    return _js("(function(){var best=null,ba=1e12;document.querySelectorAll('div,span,li,button,td,[role=option],[role=gridcell]').forEach(function(e){"
               "if(((e.innerText||'')+'').trim()!==" + json.dumps(text) + ")return;var r=e.getBoundingClientRect();if(!(r.width>0&&r.height>0)||r.width>90)return;"
               "if(e.getAttribute('aria-disabled')==='true'||/disabled|other-month|outside/i.test(e.className||''))return;var a=r.width*r.height;if(a<ba){ba=a;best=e}});"
               "if(!best)return 'false';best.click();return 'true'})()") == "true"


def schedule_tiktok(when, say) -> None:
    """Règle « Planifier » dans TikTok Studio : date et heure de mise en ligne (de 15 minutes à 10 jours à l'avance). Vérifie ce qui est affiché ensuite."""
    say(f"🗓 Programmation sur TikTok : {when:%d/%m/%Y %H:%M}…")
    if _js(_click_text_js(r"^(planifier|programmer|schedule)")) != "true":
        raise RuntimeError("option « Planifier » introuvable dans TikTok Studio")
    time.sleep(1.2)
    fields = _tt_fields()
    date_f = next((f for f in fields if f["kind"] == "date"), None)
    time_f = next((f for f in fields if f["kind"] == "time"), None)
    if not date_f or not time_f:
        raise RuntimeError(f"champs date/heure de TikTok introuvables ({fields})")
    _open_field(date_f["i"])                                              # calendrier : mois suivant si besoin, puis le jour
    for _ in range(2):
        cur = next((f for f in _tt_fields() if f["kind"] == "date"), date_f)["value"]
        if str(when.day) in re.findall(r"\d+", cur) and when.strftime("%Y") in cur and (when.strftime("%m") in cur or when.strftime("%b").lower()[:3] in cur.lower()):
            break
        if not _pick_text(str(when.day)):
            _js(_click_text_js(r"^(›|>|»|next|suivant)$"))
            time.sleep(0.6)
            _pick_text(str(when.day))
    _open_field(time_f["i"])                                              # heure : liste des heures puis des minutes (pas de 5)
    hh, mm = f"{when.hour:02d}", f"{(when.minute // 5) * 5:02d}"
    _pick_text(hh); time.sleep(0.4); _pick_text(mm)
    _js("document.body.click()"); time.sleep(0.6)
    seen = " ".join(f["value"] for f in _tt_fields())
    if f"{hh}:{mm}" not in seen.replace(" ", "") and f"{int(hh)}:{mm}" not in seen:
        raise RuntimeError(f"l'heure choisie ({hh}:{mm}) n'apparaît pas dans TikTok (valeurs lues : {seen[:80]})")


def _real_click_upload(say, strict: bool = True) -> None:
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
    if not strict:                                           # détection impossible : le bouton a bien été cliqué, on continue (la suite vérifie le résultat)
        say("⚠ Je ne vois pas la fenêtre « Ouvrir » mais j'essaie quand même.")
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


def trace(site: str, label: str) -> None:
    """Capture d'écran de l'étape (data/debug/steps/) : pour voir exactement ce que l'agent voyait si quelque chose ne va pas. Les 40 dernières sont gardées."""
    try:
        d = Path(__file__).resolve().parents[2] / "data" / "debug" / "steps"
        d.mkdir(parents=True, exist_ok=True)
        subprocess.run(["screencapture", "-x", "-t", "jpg", str(d / f"{time.strftime('%H%M%S')}_{site}_{label}.jpg")], timeout=10)
        for old in sorted(d.glob("*.jpg"))[:-40]:
            old.unlink(missing_ok=True)
    except Exception:
        pass


DUMP_JS = ("(function(){var o=[];document.querySelectorAll('input,textarea,[role=radio],[role=switch],[role=checkbox],button,[role=button],[contenteditable=true],tp-yt-paper-radio-button').forEach(function(e){"
           "var r=e.getBoundingClientRect();if(!(r.width>0&&r.height>0))return;var t=(e.innerText||e.value||e.getAttribute('aria-label')||'').trim().replace(/\\s+/g,' ').slice(0,60);"
           "o.push([e.tagName.toLowerCase(),e.type||'',e.getAttribute('name')||'',e.getAttribute('role')||'',e.getAttribute('aria-checked')||e.getAttribute('aria-pressed')||(e.checked===undefined?'':String(e.checked)),(e.value||'').slice(0,40),t].join(' | '))});"
           "return o.slice(0,150).join('\\n')})()")


def save_dump(name: str) -> str:
    """Enregistre la liste des boutons / cases / champs visibles de la page (aide à comprendre pourquoi une étape a échoué)."""
    try:
        out = Path(__file__).resolve().parents[2] / "data" / "debug" / f"{name}_page.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(_js(DUMP_JS) or "")
        return str(out)
    except Exception:
        return ""


def post(video: Path, caption: str, publish: bool = False, say=log.info, publish_at: str | None = None) -> str:
    try:
        return _post(video, caption, publish, say, publish_at)
    except Exception as e:
        shot = _shot()
        dump = save_dump("tiktok_web")
        raise RuntimeError(f"{e}" + (f" (capture d'écran : {shot})" if shot else "") + (f" (page : {dump})" if dump else "")) from e


def _tab_alive(spec: str) -> bool:
    try:
        _osa(f'tell application "{BROWSER}" to get URL of {spec}')
        return True
    except RuntimeError:
        return False


def _front_tab_spec() -> str:
    wid = _osa(f'tell application "{BROWSER}" to get id of front window')
    tid = _osa(f'tell application "{BROWSER}" to get id of active tab of front window')
    return f"tab id {tid} of window id {wid}"


def _focus_tab(spec: str) -> None:
    """Met l'onglet (déjà ouvert) au premier plan : un onglet caché est ralenti par Chrome."""
    m = re.match(r"tab id (\d+) of window id (\d+)", spec)
    if not m:
        return
    tid, wid = m.groups()
    _osa(f'tell application "{BROWSER}"\nset w to window id {wid}\nrepeat with i from 1 to count of tabs of w\n'
         f'if (id of tab i of w) is {tid} then set active tab index of w to i\nend repeat\nset index of w to 1\nactivate\nend tell')


def open_url(url: str, say, label: str, site: str = "web") -> None:
    """Ouvre `url` dans le navigateur choisi (et le bon profil Chrome). Pour une même plateforme, le MÊME onglet est réutilisé d'une vidéo à
    l'autre : aucun nouvel onglet à chaque publication."""
    global TARGET
    if BROWSER != "Safari" and site in TABS and _tab_alive(TABS[site]):
        TARGET = TABS[site]
        say(f"🌐 {label} : même onglet réutilisé")
        try:
            _js("window.onbeforeunload=null; 'ok'")                # évite la fenêtre « Quitter le site ? »
        except RuntimeError:
            pass
        _osa(f'tell application "{BROWSER}" to set URL of {TARGET} to "{url}"')
        _focus_tab(TARGET)
        time.sleep(2)
        _wait("String(document.readyState==='complete')", f"la page {label} ne se charge pas", 45)
        return
    TARGET = "active tab of front window"
    say(f"🌐 Ouverture de {label} dans {BROWSER}…")
    if BROWSER == "Safari":
        _osa(f'tell application "Safari"\nactivate\nif (count of windows) = 0 then make new document\n'
             f'set URL of current tab of front window to "{url}"\nend tell')
    elif PROFILE:                                            # ouvre la page DANS le bon profil : sa fenêtre passe au premier plan
        d = resolve_profile(PROFILE)
        say(f"👤 Profil Chrome utilisé : {d}")
        subprocess.run(["open", "-na", BROWSER, "--args", f"--profile-directory={d}", url], check=True)   # -n : sinon Chrome déjà lancé ignore le profil demandé
        time.sleep(3)
        _osa(f'tell application "{BROWSER}" to activate')
    else:
        try:
            _osa(f'tell application "{BROWSER}"\nactivate\nif (count of windows) = 0 then make new window\n'
                 f'set URL of active tab of front window to "{url}"\nend tell')
        except RuntimeError as e:
            profs = ", ".join(f"« {p['name']} »" for p in chrome_profiles())
            raise RuntimeError("Chrome n'a pas de fenêtre de navigation (il affiche peut-être « Qui utilise Chrome ? »). Indique le profil du compte dans "
                               "config/settings.yaml (ligne chrome_profile)" + (f" : {profs}" if profs else "") + f". Détail : {str(e)[:120]}") from e
    say(f"🔐 Test du réglage JavaScript de {BROWSER}…")
    _wait("String(1+1==2)", f"{BROWSER} n'a pas ouvert de fenêtre de navigation (vérifie le profil dans chrome_profile)", 25)
    if BROWSER != "Safari" and site != "web":
        try:
            TABS[site] = TARGET = _front_tab_spec()                # on retient l'onglet pour les vidéos suivantes
        except RuntimeError:
            pass


INJECT_CHUNK = 240_000          # caractères base64 par appel (une ligne de commande macOS est limitée à ~1 Mo)


def inject_file(path, say) -> None:
    """Donne le fichier directement à la page (<input type=file>), comme un glisser-déposer : aucune fenêtre « Ouvrir », aucun clic, aucun clavier.
    Le fichier est transmis en morceaux base64 puis reconstitué dans la page."""
    import base64
    path = Path(path)
    raw = path.read_bytes()
    b64 = base64.b64encode(raw).decode()
    say(f"📦 Envoi du fichier à la page ({len(raw) / 1e6:.1f} Mo)…")
    if _js('String(!!document.querySelector("input[type=file]"))') != "true":
        raise RuntimeError("zone d'envoi de fichier introuvable sur la page")
    _js('window.__pf=[]; "ok"')
    for i in range(0, len(b64), INJECT_CHUNK):
        _js(f'window.__pf.push("{b64[i:i + INJECT_CHUNK]}"); "ok"')
    name = path.name.replace('"', "")
    ok = _js('(function(){try{var s=atob(window.__pf.join(""));var u=new Uint8Array(s.length);for(var i=0;i<s.length;i++)u[i]=s.charCodeAt(i);'
             f'var f=new File([u],"{name}",{{type:"video/mp4"}});var dt=new DataTransfer();dt.items.add(f);'
             'var inp=document.querySelector("input[type=file]");inp.files=dt.files;'
             'inp.dispatchEvent(new Event("input",{bubbles:true}));inp.dispatchEvent(new Event("change",{bubbles:true}));window.__pf=null;'
             'return inp.files.length==1?"true":"false"}catch(e){return "err:"+e.message}})()')
    if ok != "true":
        raise RuntimeError(f"la page a refusé le fichier ({ok})")


def _dialog_pick(path, say) -> None:
    """Plan B : vrai clic sur le bouton, puis fenêtre « Ouvrir » de macOS (⇧⌘G -> chemin collé -> Entrée)."""
    say("📁 Sélection du fichier avec la fenêtre « Ouvrir »…")
    _real_click_upload(say, strict=False)
    time.sleep(0.8)
    _clip(str(path))
    _keys('keystroke "g" using {command down, shift down}', "delay 1", 'keystroke "v" using command down', "delay 1",
          "key code 36", "delay 1.5", "key code 36")


def choose_file(path, say, verify: str | None = None, wait: int = 30) -> None:
    """Envoie la vidéo à la page. 1) injection directe ; 2) si la page ne réagit pas (`verify` = expression JavaScript qui devient « true »
    quand l'envoi a démarré) ou refuse le fichier : vrai clic + fenêtre « Ouvrir »."""
    try:
        inject_file(path, say)
    except RuntimeError as e:
        say(f"↪ Envoi direct impossible ({str(e)[:90]}) : j'essaie avec la fenêtre « Ouvrir »…")
        return _dialog_pick(path, say)
    if verify is None:
        return
    end = time.monotonic() + wait
    while time.monotonic() < end:
        try:
            if _js(verify) == "true":
                return
        except RuntimeError:
            pass
        time.sleep(2)
    say("↪ La page n'a pas réagi à l'envoi direct : j'essaie avec la fenêtre « Ouvrir »…")
    _dialog_pick(path, say)


def _post(video, caption, publish, say, publish_at=None):
    video = Path(video).resolve()
    if not video.exists():
        raise RuntimeError(f"vidéo introuvable : {video}")
    open_url(UPLOAD_URL, say, "TikTok Studio", site="tiktok")
    _wait('String(!!document.querySelector("input[type=file]"))', "page d'envoi non chargée")
    if _js('String(/connecter|log in|se connecter/i.test(document.body.innerText.slice(0,400)) && !document.querySelector("input[type=file]"))') == "true":
        raise RuntimeError("TikTok demande de se connecter : connecte ton compte dans Safari puis relance")
    choose_file(video, say, verify='String(!!document.querySelector("[contenteditable=true]"))')
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
    typed = _js('var e=document.querySelector("[contenteditable=true]");e?(e.innerText||e.textContent||"").trim():""')
    if len(typed) < min(len(body), 8):                                       # légende vide ou perdue : on s'arrête au lieu de publier sans texte
        raise RuntimeError(f"la légende n'a pas été écrite dans TikTok (lu : « {typed[:40]} »)")
    trace("tiktok", "1_legende")
    when = None
    if publish_at:
        from datetime import datetime
        when = datetime.fromisoformat(publish_at)
        schedule_tiktok(when, say)
        trace("tiktok", "2_programmation")
    if not publish:
        say("✋ Tout est prêt dans le navigateur : vérifie puis clique sur « Publier » toi-même.")
        return "prêt (non publié)"
    say("🚀 Clic sur « Planifier »…" if when else "🚀 Clic sur « Publier »…")
    pat = "planifier|programmer|schedule" if when else "publier|post"
    ok = _js('var b=[...document.querySelectorAll("button")].find(x=>/^(' + pat + ')$/i.test(x.innerText.trim())&&!x.disabled);'
             'if(b){b.click();"true"}else{"false"}')
    if ok != "true":
        raise RuntimeError("bouton « Publier » introuvable ou grisé (vidéo encore en traitement ?)")
    time.sleep(4)
    _js('var b=[...document.querySelectorAll("button")].find(x=>/^(publier maintenant|post now|confirmer|confirm|planifier|schedule)$/i.test(x.innerText.trim())&&!x.disabled&&x.getBoundingClientRect().width>0&&document.querySelectorAll("[role=dialog],.TUXModal,.modal").length>0); if(b)b.click(); "ok"')
    end = time.monotonic() + 40                                              # TikTok doit CONFIRMER : on ne dit « publié » que si c'est vrai
    done = False
    while time.monotonic() < end:
        if _js('String(/publi[ée]e?|planifi[ée]e?|programm[ée]e?|t[ée]l[ée]vers[ée]e?|has been|scheduled|uploaded|manage your posts|g[ée]rer vos publications/i.test(document.body.innerText)'
               ' && !document.querySelector("input[type=file]:not([hidden])") || !/upload/.test(location.pathname))') == "true":
            done = True
            break
        time.sleep(2)
    trace("tiktok", "3_apres_publication")
    if not done:
        raise RuntimeError("TikTok n'a pas confirmé la publication (la page est restée sur l'envoi)")
    return f"programmée le {when:%d/%m/%Y à %H:%M}" if when else "publié"


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
        pa = meta.get("publish_at")
        try:
            st = post(video, cap, self.go or bool(pa), publish_at=pa)
        except Exception as e:
            return Result(self.platform, "FAILED", "", f"{e}")
        return Result(self.platform, "SCHEDULED" if pa else ("PUBLISHED" if self.go else "EXPORTED"), key, st)
