import random

HOOKS = ["Tu connais ce morceau ?", "Essaie de le jouer en 1 minute", "Ce passage est incroyable", "Piano satisfaisant",
         "Les notes qui tombent... hypnotisant", "Apprends ce morceau facilement", "Le piano comme tu ne l'as jamais vu",
         "Regarde jusqu'à la fin", "Ça sonne tellement bien", "Un classique que tout le monde reconnaît"]
CTA = ["Suis-moi pour plus de piano", "Dis-moi le prochain morceau en commentaire", "Sauvegarde pour t'entraîner",
       "Partage à un pianiste !", "Abonne-toi pour la suite"]
TAGS = ["#piano", "#pianotutorial", "#learnpiano", "#pianocover", "#synthesia", "#music", "#fyp", "#pianomusic",
        "#pianist", "#classicalmusic", "#satisfying", "#pourtoi"]
LEVEL = {"Débutant": "débutant", "Facile": "facile", "Moyen": "intermédiaire", "Difficile": "difficile", "Expert": "expert", "Avancé": "avancé"}


def generate(song: dict, difficulty: str, seed: int, used_titles: set[str], bpm: float | None = None) -> dict:
    rnd = random.Random(seed)
    for _ in range(30):
        hook = rnd.choice(HOOKS)
        title = f"{song['title']} - {hook}"[:95]
        if title not in used_titles:
            break
    cta = rnd.choice(CTA)
    tags = rnd.sample(TAGS, 5)
    level = LEVEL.get(difficulty, difficulty)
    if bpm:
        level = f"{level} ({round(bpm)} BPM)"
    body = f"{song['title']} - {song['artist']}"
    desc = f"{hook}\n\n{body}\nNiveau : {level}\n\n{cta}\n\n" + " ".join(tags)
    return {
        "title": title, "description": desc, "hashtags": tags, "difficulty": difficulty,
        "hook": hook, "cta": cta, "level": difficulty, "bpm": round(bpm) if bpm else None,                                   # texte à l'écran (début / fin)
        "keywords": [song["title"], song["artist"], "piano tutorial"],
        "tiktok_caption": f"{hook} {body} " + " ".join(tags),      # ~ légende courte
        "instagram_caption": f"{hook}\n{body}\n{cta}\n.\n" + " ".join(tags + ["#reels"]),
        "youtube_title": title, "pinned_comment": f"Quel morceau voulez-vous ensuite ? ({level})",
    }


def difficulty_of(analysis: dict) -> str:
    d = analysis["avg_density"]
    return "Facile" if d < 3 else "Moyen" if d < 6 else "Avancé"
