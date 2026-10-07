"""Synthèse piano additive (numpy) : audio sans dépendre d'un logiciel externe."""
import wave
import numpy as np

SR = 44100
_HARM = [1.0, 0.55, 0.30, 0.18, 0.10, 0.06]


def render_audio(notes, start: float, duration: float) -> np.ndarray:
    buf = np.zeros(int(duration * SR) + SR, dtype=np.float64)
    for n in notes:
        if n.end <= start or n.start >= start + duration:
            continue
        t0 = n.start - start
        hold = max(min(n.end, start + duration) - max(n.start, start), 0.08)
        length = int((hold + 0.6) * SR)
        t = np.arange(length) / SR
        f = 440.0 * 2 ** ((n.pitch - 69) / 12)
        wave_ = sum(a * np.sin(2 * np.pi * f * (k + 1) * t * (1 + 0.0002 * k * k)) for k, a in enumerate(_HARM) if f * (k + 1) < SR / 2)
        decay = np.exp(-t * (1.2 + f / 900))                      # corde qui s'éteint
        rel = np.where(t > hold, np.exp(-(t - hold) * 18), 1.0)    # relâchement
        att = np.minimum(t / 0.004, 1.0)
        env = decay * rel * att * (n.velocity / 127) ** 1.2
        i0 = int(max(t0, 0) * SR) if t0 >= 0 else 0
        seg = (wave_ * env)[(-int(t0 * SR) if t0 < 0 else 0):]
        buf[i0:i0 + len(seg)] += seg[:len(buf) - i0]
    buf = buf[:int(duration * SR)]
    peak = np.abs(buf).max()
    if peak > 0:
        buf = np.tanh(buf / peak * 1.6) / np.tanh(1.6) * 0.89  # limiteur doux
    fade = min(int(0.4 * SR), len(buf))
    buf[-fade:] *= np.linspace(1, 0, fade)
    return buf


def write_wav(path, audio: np.ndarray):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes())
