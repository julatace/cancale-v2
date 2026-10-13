"""Textes des vidéos « rebonds » : titre numéroté comme une série, accroche, description, hashtags (tendances « satisfying »)."""
import random
import re
import unicodedata

HOOKS = {
    "fr": ["La balle qui joue la musique", "Satisfaisant : la balle suit la mélodie", "Regarde jusqu'à la fin", "Chaque rebond est une note",
           "Tu reconnais le morceau ?", "Le parcours le plus satisfaisant", "Musique et rebonds en parfaite synchro"],
    "en": ["The ball that plays the music", "Satisfying: the ball follows the melody", "Watch until the end", "Every bounce is a note",
           "Can you name the song?", "The most satisfying run", "Music and bounces in perfect sync"],
}
CTA = {"fr": ["Suis-moi pour la suite", "Dis-moi le prochain morceau en commentaire", "Sauvegarde pour te détendre"],
       "en": ["Follow for more", "Tell me the next song in the comments", "Save it to relax"]}
BASE_TAGS = ["#satisfying", "#oddlysatisfying", "#asmr", "#marblerun", "#fyp"]


def _slug(t: str) -> str:
    s = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", s)


def _short(t: str, n: int = 26) -> str:
    t = re.sub(r"\s+", " ", (t or "").strip())
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0].rstrip(",.- ") + "…"


def generate(meta: dict, number: int, seed: int, used_titles: set, lang: str = "fr") -> dict:
    lang = lang if lang in HOOKS else "fr"
    from app.director.pipeline import clean_artist
    rnd = random.Random(seed)
    song = (meta.get("title") or "Morceau").strip()
    artist = clean_artist(meta.get("artist"))
    artist = "" if artist.lower() in ("", "unknown", "inconnu") else artist
    seen = {t.rsplit(" - ", 1)[-1] for t in used_titles}
    fresh = [h for h in HOOKS[lang] if h not in seen] or HOOKS[lang]
    hook = rnd.choice(fresh)
    title = f"{song} - {hook}"[:95]
    tags = list(BASE_TAGS)
    s = _slug(song)
    if 4 <= len(s) <= 24:
        tags.append("#" + s)
    if artist:
        last = _slug(artist.split()[-1])
        if 3 <= len(last) <= 20:
            tags.append("#" + last)
    tags = tags[:7]
    cta = rnd.choice(CTA[lang])
    body = f"{song} - {artist}" if artist else song
    desc = f"{hook}\n\n{body}\n\n{cta}\n\n" + " ".join(tags)
    return {"title": title, "description": desc, "hashtags": tags, "youtube_title": title, "tiktok_caption": f"{hook} {body} " + " ".join(tags),
            "instagram_caption": f"{hook}\n{body}\n{cta}\n.\n" + " ".join(tags + ["#reels"]), "pinned_comment": cta,
            "hook": hook, "cta": cta, "label": f"{number}. {_short(song)}", "song_title": song, "song_artist": artist, "shorts": True}
