import random

# Textes par langue : accroche affichée au début de la vidéo, appel à l'action de fin, niveaux, hashtags.
LANGS = {
    "fr": {
        "hooks": ["Tu connais ce morceau ?", "Essaie de le jouer en 1 minute", "Ce passage est incroyable", "Piano satisfaisant",
                  "Les notes qui tombent... hypnotisant", "Apprends ce morceau facilement", "Le piano comme tu ne l'as jamais vu",
                  "Regarde jusqu'à la fin", "Ça sonne tellement bien", "Un classique que tout le monde reconnaît"],
        "cta": ["Suis-moi pour plus de piano", "Dis-moi le prochain morceau en commentaire", "Sauvegarde pour t'entraîner",
                "Partage à un pianiste !", "Abonne-toi pour la suite"],
        "tags": ["#piano", "#pianotutorial", "#learnpiano", "#pianocover", "#synthesia", "#music", "#fyp", "#pianomusic", "#pianist",
                 "#classicalmusic", "#satisfying", "#pourtoi"],
        "level": {"Débutant": "débutant", "Facile": "facile", "Moyen": "intermédiaire", "Difficile": "difficile", "Expert": "expert", "Avancé": "avancé"},
        "level_word": "Niveau", "pinned": "Quel morceau voulez-vous ensuite ? ({level})",
    },
    "en": {
        "hooks": ["Do you know this piece?", "Try playing it in 1 minute", "This part is incredible", "Satisfying piano",
                  "Falling notes... so hypnotic", "Learn this piece easily", "Piano like you've never seen it",
                  "Watch until the end", "It sounds so good", "A classic everyone recognizes"],
        "cta": ["Follow for more piano", "Tell me the next piece in the comments", "Save it to practice later",
                "Share it with a pianist!", "Subscribe for more"],
        "tags": ["#piano", "#pianotutorial", "#learnpiano", "#pianocover", "#synthesia", "#music", "#fyp", "#pianomusic", "#pianist",
                 "#classicalmusic", "#satisfying", "#foryou"],
        "level": {"Débutant": "beginner", "Facile": "easy", "Moyen": "intermediate", "Difficile": "hard", "Expert": "expert", "Avancé": "advanced"},
        "level_word": "Level", "pinned": "Which piece next? ({level})",
    },
    "es": {
        "hooks": ["¿Conoces esta pieza?", "Intenta tocarla en 1 minuto", "Este pasaje es increíble", "Piano relajante",
                  "Notas que caen... hipnótico", "Aprende esta pieza fácilmente", "El piano como nunca lo has visto",
                  "Mira hasta el final", "Suena genial", "Un clásico que todos reconocen"],
        "cta": ["Sígueme para más piano", "Dime la próxima pieza en los comentarios", "Guárdalo para practicar",
                "¡Compártelo con un pianista!", "Suscríbete para más"],
        "tags": ["#piano", "#pianotutorial", "#aprenderpiano", "#pianocover", "#synthesia", "#musica", "#fyp", "#pianomusic", "#pianista",
                 "#musicaclasica", "#satisfactorio", "#parati"],
        "level": {"Débutant": "principiante", "Facile": "fácil", "Moyen": "intermedio", "Difficile": "difícil", "Expert": "experto", "Avancé": "avanzado"},
        "level_word": "Nivel", "pinned": "¿Qué pieza quieres después? ({level})",
    },
}
# compatibilité (français par défaut)
HOOKS, CTA, TAGS, LEVEL = LANGS["fr"]["hooks"], LANGS["fr"]["cta"], LANGS["fr"]["tags"], LANGS["fr"]["level"]


def _slug(text: str) -> str:
    import re
    import unicodedata
    s = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", s)


def _tags_for(song: dict, L: dict, rnd: random.Random) -> list[str]:
    """Hashtags ciblés : ceux du morceau et du compositeur d'abord, puis des tags piano variés, 7 au total."""
    own = []
    artist = song.get("artist") or ""
    if artist and artist.lower() != "unknown":
        last = _slug(artist.split()[-1]) if len(artist.split()) > 1 else _slug(artist)   # « J. S. Bach » -> #bach
        if 3 <= len(last) <= 24:
            own.append("#" + last)
    title = _slug(song.get("title", ""))
    if 4 <= len(title) <= 24:
        own.append("#" + title)
    base = ["#piano", "#fyp"]
    rest = [x for x in L["tags"] if x not in base]
    pick = rnd.sample(rest, min(7 - len(own) - len(base), len(rest)))
    out, seen = [], set()
    for h in own + base + pick:
        if h.lower() not in seen:
            seen.add(h.lower()); out.append(h)
    return out[:7]


def generate(song: dict, difficulty: str, seed: int, used_titles: set[str], bpm: float | None = None, lang: str = "fr") -> dict:
    L = LANGS.get(lang, LANGS["fr"])
    rnd = random.Random(seed)
    for _ in range(30):
        hook = rnd.choice(L["hooks"])
        title = f"{song['title']} - {hook}"[:95]
        if title not in used_titles:
            break
    cta = rnd.choice(L["cta"])
    tags = _tags_for(song, L, rnd)
    level = L["level"].get(difficulty, difficulty)
    if bpm:
        level = f"{level} ({round(bpm)} BPM)"
    body = f"{song['title']} - {song['artist']}" if song.get("artist") and song["artist"].lower() != "unknown" else song["title"]
    desc = f"{hook}\n\n{body}\n{L['level_word']} : {level}\n\n{cta}\n\n" + " ".join(tags)
    return {
        "title": title, "description": desc, "hashtags": tags, "difficulty": difficulty, "lang": lang,
        "hook": hook, "cta": cta, "level": difficulty, "bpm": round(bpm) if bpm else None,
        "keywords": [song["title"], song["artist"], "piano tutorial"],
        "tiktok_caption": f"{hook} {body} " + " ".join(tags),
        "instagram_caption": f"{hook}\n{body}\n{cta}\n.\n" + " ".join(tags + ["#reels"]),
        "youtube_title": title, "pinned_comment": L["pinned"].format(level=level),
    }


def difficulty_of(analysis: dict) -> str:
    d = analysis["avg_density"]
    return "Facile" if d < 3 else "Moyen" if d < 6 else "Avancé"
