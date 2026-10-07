"""Écriture MIDI (SMF 0) minimale."""
import struct


def vlq(n):
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80); n >>= 7
    return bytes(reversed(out))


def make_midi(events, ppq=480, bpm=120):
    """events: [(start_beat, dur_beat, pitch, vel)] -> bytes SMF format 0."""
    tempo = b"\x00\xff\x51\x03" + int(60e6 / bpm).to_bytes(3, "big")
    ev = []
    for s, d, p, v in events:
        ev.append((int(s * ppq), 1, 0x90, p, v)); ev.append((int((s + d) * ppq), 0, 0x80, p, 0))
    ev.sort()
    body, last = tempo, 0
    for t, _, st, p, v in ev:
        body += vlq(t - last) + bytes([st, p, v]); last = t
    body += b"\x00\xff\x2f\x00"
    return b"MThd" + struct.pack(">IHHH", 6, 0, 1, ppq) + b"MTrk" + struct.pack(">I", len(body)) + body


