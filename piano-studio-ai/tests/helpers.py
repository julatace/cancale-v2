from app.midi_analyzer.writer import make_midi, vlq  # noqa


def song(sparse_beats=16, busy_beats=32):
    """Intro clairsemée puis passage dense à deux mains (120 bpm -> 2 beats/s)."""
    ev = [(b, 0.5, 60, 60) for b in range(0, sparse_beats, 4)]
    for b in range(sparse_beats * 1, sparse_beats + busy_beats):
        ev += [(b, 0.5, 72 + b % 12, 100), (b + 0.5, 0.5, 48 + b % 5, 100), (b, 1, 40, 100), (b, 1, 76, 100)]
    return make_midi(ev)


def make_band_smf(ppq=480, bpm=100):
    """Fichier de groupe type karaoké : piste 'Chant' (avec des paroles factices), 'Basse', 'Piano' d'accords, 'Drums' (canal 10)."""
    import struct

    def trk(name, channel, program, notes, texts=0):
        ev = [(0, 0, b"\xff\x03" + bytes([len(name)]) + name.encode())]
        ev.append((0, 0, bytes([0xC0 | channel, program])))
        for i in range(texts):
            ev.append((int(i * 0.5 * ppq), 0, b"\xff\x05\x02la"))
        for s, d, p, v in notes:
            ev.append((int(s * ppq), 1, bytes([0x90 | channel, p, v])))
            ev.append((int((s + d) * ppq), 0, bytes([0x80 | channel, p, 0])))
        ev.sort(key=lambda e: (e[0], e[1]))
        body, last = b"", 0
        for tick, _, raw in ev:
            body += vlq(tick - last) + raw; last = tick
        body += b"\x00\xff\x2f\x00"
        return b"MTrk" + struct.pack(">I", len(body)) + body

    tempo = b"\x00\xff\x51\x03" + int(60e6 / bpm).to_bytes(3, "big") + b"\x00\xff\x2f\x00"
    tracks = [b"MTrk" + struct.pack(">I", len(tempo)) + tempo,
              trk("Chant", 0, 73, [(i * 0.5, 0.4, 72 + (i * 3) % 9, 90) for i in range(160)], texts=120),
              trk("Basse", 1, 33, [(i * 1.0, 0.9, 40 + (i % 4) * 2, 85) for i in range(80)]),
              trk("Piano", 2, 0, [(i * 2.0, 1.8, p, 70) for i in range(40) for p in (55, 59, 62)]),
              trk("Guitare", 3, 25, [(i * 0.25, 0.2, 50 + i % 7, 60) for i in range(320)]),         # trop chargée : doit être écartée
              trk("Drums", 9, 0, [(i * 0.25, 0.1, 36 + i % 3, 100) for i in range(320)])]            # batterie : jamais jouée
    return b"MThd" + struct.pack(">IHHH", 6, 1, len(tracks), ppq) + b"".join(tracks)
