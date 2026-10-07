"""Parseur MIDI (SMF 0/1) minimal, sans dépendance. Retourne des notes en secondes."""
from dataclasses import dataclass
import struct


@dataclass(frozen=True)
class Note:
    start: float
    end: float
    pitch: int
    velocity: int
    track: int
    channel: int = 0


class MidiError(ValueError):
    pass


def _vlq(data, i):
    v = 0
    while True:
        if i >= len(data):
            raise MidiError("VLQ tronqué")
        b = data[i]; i += 1
        v = (v << 7) | (b & 0x7F)
        if not b & 0x80:
            return v, i


def parse_midi(path_or_bytes) -> tuple[list[Note], list[tuple[float, float]]]:
    """Retourne (notes, tempo_map[(sec, bpm)])."""
    data = path_or_bytes if isinstance(path_or_bytes, (bytes, bytearray)) else open(path_or_bytes, "rb").read()
    if data[:4] != b"MThd" or len(data) < 14:
        raise MidiError("pas un fichier MIDI")
    _fmt, ntrk, div = struct.unpack(">HHH", data[8:14])
    if div & 0x8000:
        raise MidiError("division SMPTE non supportée")
    i = 8 + struct.unpack(">I", data[4:8])[0]
    tracks, tempo_events = [], []  # events: (tick, kind, a, b, track)
    for t in range(ntrk):
        if data[i:i + 4] != b"MTrk":
            raise MidiError("chunk de piste invalide")
        ln = struct.unpack(">I", data[i + 4:i + 8])[0]
        j, end, tick, status = i + 8, i + 8 + ln, 0, 0
        if end > len(data):
            raise MidiError("piste tronquée")
        while j < end:
            d, j = _vlq(data, j); tick += d
            if data[j] & 0x80:
                status = data[j]; j += 1
            if status == 0xFF:
                typ = data[j]; l, j = _vlq(data, j + 1)
                if typ == 0x51 and l == 3:
                    tempo_events.append((tick, int.from_bytes(data[j:j + 3], "big")))
                j += l
            elif status in (0xF0, 0xF7):
                l, j = _vlq(data, j); j += l
            else:
                kind = status & 0xF0
                n = 1 if kind in (0xC0, 0xD0) else 2
                a = data[j]; b = data[j + 1] if n == 2 else 0
                j += n
                if status & 0x0F == 9:
                    continue                               # canal 10 = batterie : jamais joué au piano
                if kind == 0x90 and b > 0:
                    tracks.append((tick, "on", a, b, t, status & 0x0F))
                elif kind == 0x80 or (kind == 0x90 and b == 0):
                    tracks.append((tick, "off", a, 0, t, status & 0x0F))
        i = end
    tempo_events.sort()
    if not tempo_events or tempo_events[0][0] != 0:
        tempo_events.insert(0, (0, 500000))
    # tick -> secondes via la tempo map
    segs, sec = [], 0.0
    for k, (tk, us) in enumerate(tempo_events):
        segs.append((tk, sec, us))
        if k + 1 < len(tempo_events):
            sec += (tempo_events[k + 1][0] - tk) * us / 1e6 / div

    def to_sec(tick):
        tk, s, us = [x for x in segs if x[0] <= tick][-1]
        return s + (tick - tk) * us / 1e6 / div

    tracks.sort(key=lambda e: (e[0], e[1] == "on"))
    open_notes, notes = {}, []
    for tick, kind, p, v, t, ch in tracks:
        key = (t, ch, p)
        if kind == "on":
            open_notes.setdefault(key, []).append((tick, v))
        elif open_notes.get(key):
            st, vel = open_notes[key].pop(0)
            if tick > st:
                notes.append(Note(to_sec(st), to_sec(tick), p, vel, t, ch))
    notes.sort(key=lambda n: (n.start, n.pitch))
    tempo_map = [(s, 60e6 / us) for _, s, us in segs]
    return notes, tempo_map


def parse_midi_info(path_or_bytes) -> dict[int, dict]:
    """Par piste : nom, programmes (instruments GM), nombre d'événements de texte/paroles (fichiers karaoké). Les paroles ne sont pas lues."""
    data = path_or_bytes if isinstance(path_or_bytes, (bytes, bytearray)) else open(path_or_bytes, "rb").read()
    if data[:4] != b"MThd":
        raise MidiError("pas un fichier MIDI")
    ntrk = struct.unpack(">H", data[10:12])[0]
    i = 8 + struct.unpack(">I", data[4:8])[0]
    info = {}
    for t in range(ntrk):
        if data[i:i + 4] != b"MTrk":
            break
        ln = struct.unpack(">I", data[i + 4:i + 8])[0]
        j, end, status = i + 8, i + 8 + ln, 0
        rec = {"name": "", "programs": set(), "texts": 0}
        while j < min(end, len(data)):
            _, j = _vlq(data, j)
            if data[j] & 0x80:
                status = data[j]; j += 1
            if status == 0xFF:
                typ = data[j]; l, j = _vlq(data, j + 1)
                if typ == 0x03: rec["name"] = data[j:j + l].decode("latin-1", "replace")[:40]
                if typ in (0x01, 0x05): rec["texts"] += 1
                j += l
            elif status in (0xF0, 0xF7):
                l, j = _vlq(data, j); j += l
            else:
                k = status & 0xF0
                if k == 0xC0: rec["programs"].add(data[j])
                j += 1 if k in (0xC0, 0xD0) else 2
        info[t] = rec
        i = end
    return info
