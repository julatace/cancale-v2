import random

HOOKS = ["Tu connais ce morceau ?", "Essaie de le jouer en 1 minute 🎹", "Ce passage est incroyable", "Piano satisfaisant 🎶",
         "Les notes qui tombent… hypnotisant", "Apprends ce morceau facilement", "Le piano comme tu ne l'as jamais vu"]
CTA = ["Abonne-toi pour la suite 🎹", "Dis-moi le prochain morceau en commentaire", "Sauvegarde pour t'entraîner plus tard", "Partage à un pianiste !"]
TAGS = ["#piano", "#pianotutorial", "#learnpiano", "#pianocover", "#synthesia", "#music", "#fyp", "#pianomusic", "#pianist", "#shorts"]


def generate(song: dict, difficulty: str, seed: int, used_titles: set[str]) -> dict:
    rnd = random.Random(seed)
    for _ in range(20):
        hook = rnd.choice(HOOKS)
        title = f"{song['title']} – {hook}"[:95]
        if title not in used_titles:
            break
    tags = rnd.sample(TAGS, 6)
    desc = (f"{hook}\n\n🎵 {song['title']} — {song['artist']}\nDifficulté : {difficulty}\n\n{rnd.choice(CTA)}\n\n" + " ".join(tags))
    return {"title": title, "description": desc, "hashtags": tags, "cta": CTA and rnd.choice(CTA),
            "keywords": [song["title"], song["artist"], "piano tutorial"], "difficulty": difficulty}


def difficulty_of(analysis: dict) -> str:
    d = analysis["avg_density"]
    return "Facile" if d < 3 else "Moyen" if d < 6 else "Avancé"
