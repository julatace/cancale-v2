from app.midi_analyzer.writer import make_midi, vlq  # noqa


def song(sparse_beats=16, busy_beats=32):
    """Intro clairsemée puis passage dense à deux mains (120 bpm -> 2 beats/s)."""
    ev = [(b, 0.5, 60, 60) for b in range(0, sparse_beats, 4)]
    for b in range(sparse_beats * 1, sparse_beats + busy_beats):
        ev += [(b, 0.5, 72 + b % 12, 100), (b + 0.5, 0.5, 48 + b % 5, 100), (b, 1, 40, 100), (b, 1, 76, 100)]
    return make_midi(ev)
