"""Source 100 % légale et autonome : compositions originales générées + mélodies du domaine public
(transcrites ici : aucune tierce partie ne détient de droits dessus)."""
import random

from app.midi_analyzer.writer import make_midi

NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
MAJ, MIN = [0, 2, 4, 5, 7, 9, 11], [0, 2, 3, 5, 7, 8, 10]
PROGS = {"major": [[0, 4, 5, 3], [0, 5, 3, 4], [5, 3, 0, 4], [0, 3, 4, 4]],
         "minor": [[0, 5, 2, 6], [0, 3, 6, 4], [5, 6, 0, 0], [0, 6, 5, 4]]}

PD_SONGS = {  # (titre, compositeur, mode, [(pitch, beats)])  — mélodies du domaine public
    "Ode to Joy": ("Beethoven", 60, [(64, 1), (64, 1), (65, 1), (67, 1), (67, 1), (65, 1), (64, 1), (62, 1), (60, 1), (60, 1), (62, 1), (64, 1), (64, 1.5), (62, .5), (62, 2),
                                      (64, 1), (64, 1), (65, 1), (67, 1), (67, 1), (65, 1), (64, 1), (62, 1), (60, 1), (60, 1), (62, 1), (64, 1), (62, 1.5), (60, .5), (60, 2)]),
    "Für Elise": ("Beethoven", 57, [(76, .5), (75, .5), (76, .5), (75, .5), (76, .5), (71, .5), (74, .5), (72, .5), (69, 1.5), (60, .5), (64, .5), (69, .5), (71, 1.5), (64, .5), (68, .5), (71, .5), (72, 1.5), (64, .5),
                                (76, .5), (75, .5), (76, .5), (75, .5), (76, .5), (71, .5), (74, .5), (72, .5), (69, 1.5), (60, .5), (64, .5), (69, .5), (71, 1.5), (64, .5), (72, .5), (71, .5), (69, 2)]),
}


def _scale(root, mode):
    return [root + s for s in (MAJ if mode == "major" else MIN)]


def _triad(sc, deg):
    return [sc[deg % 7], sc[(deg + 2) % 7] + (12 if (deg + 2) >= 7 else 0), sc[(deg + 4) % 7] + (12 if (deg + 4) >= 7 else 0)]


def compose(seed: int) -> tuple[bytes, dict]:
    rnd = random.Random(seed)
    mode = rnd.choice(["major", "minor"])
    tonic = rnd.randrange(0, 12)
    bpm = rnd.choice([84, 92, 100, 108, 116])
    prog = rnd.choice(PROGS[mode])
    sc_low, sc_high = _scale(48 + tonic % 12, mode), _scale(72 + tonic % 12 - 12 * (tonic > 6), mode)
    ev = []
    beat = 0.0
    sections = [("verse", 2), ("verse2", 2), ("chorus", 4), ("chorus", 4)]
    mel_deg = rnd.randrange(0, 7)
    for name, reps in sections:
        chorus = name == "chorus"
        for _ in range(reps):
            for deg in prog:
                ch = _triad(sc_low, deg)
                # main gauche : arpège (plus dense au refrain)
                step = 0.25 if chorus else 0.5
                pat = [ch[0], ch[1], ch[2], ch[1]] if not chorus else [ch[0], ch[1], ch[2], ch[1] + 12, ch[2], ch[1]]
                for i in range(int(4 / step)):
                    ev.append((beat + i * step, step * 0.95, pat[i % len(pat)] - (12 if i == 0 else 0), 70 + (15 if chorus else 0) + (10 if i % 4 == 0 else 0)))
                # main droite : mélodie par degrés conjoints
                t = 0.0
                rhythm = rnd.choice([[1, 1, 2], [1.5, .5, 1, 1], [.5, .5, 1, 2], [1, .5, .5, 2]]) if not chorus else rnd.choice([[.5] * 8, [1, .5, .5, 1, 1], [.5, .5, .5, .5, 1, 1]])
                for d in rhythm:
                    mel_deg = max(0, min(13, mel_deg + rnd.choice([-2, -1, -1, 0, 1, 1, 2])))
                    if t == 0 and rnd.random() < .7:
                        mel_deg = (deg + rnd.choice([0, 2, 4]) ) % 7 + 7
                    p = sc_high[mel_deg % 7] + 12 * (mel_deg // 7) - 12
                    vel = 85 + (20 if chorus else 0)
                    ev.append((beat + t, d * 0.95, p, vel))
                    if chorus and t % 1 == 0:
                        ev.append((beat + t, d * 0.95, p - 12, vel - 20))  # octave
                    t += d
                    if t >= 4: break
                beat += 4
    title = f"Original Piano Piece #{seed}"
    return make_midi(ev, bpm=bpm), {"title": title, "artist": "Piano Studio AI", "key": f"{NAMES[tonic]} {mode}", "bpm": bpm}


def pd_song(name: str) -> tuple[bytes, dict]:
    comp, lo, mel = PD_SONGS[name]
    ev, b = [], 0.0
    for _ in range(2):
        for p, d in mel:
            ev.append((b, d * 0.95, p + 12 if p < lo + 4 else p, 95))
            if int(b) % 2 == 0 and b == int(b):
                ev.append((b, 2, lo - 12 + (0 if int(b) % 4 == 0 else 7), 70))
            b += d
    return make_midi(ev, bpm=96), {"title": name, "artist": f"{comp} (public domain)", "bpm": 96}
