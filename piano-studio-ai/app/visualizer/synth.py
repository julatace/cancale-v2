"""Piano de secours (numpy) : plusieurs cordes légèrement désaccordées, harmoniques qui s'éteignent à des vitesses différentes,
bruit de marteau, stéréo selon la hauteur et réverbération douce. Sur Mac, le piano du système (afconvert) est préféré."""
import wave

import numpy as np

SR = 44100
K = 8                          # nombre d'harmoniques


def _reverb(x: np.ndarray, wet=0.14, seconds=0.9, seed=0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / SR / 0.28)
    ir[: int(0.01 * SR)] *= np.linspace(0, 1, int(0.01 * SR))
    ir /= np.abs(ir).sum() ** 0.5 * 12
    block = 1 << 16
    size = block + n - 1
    nfft = 1 << (size - 1).bit_length()
    H = np.fft.rfft(ir, nfft)
    out = np.zeros(len(x) + n)
    for i in range(0, len(x), block):
        seg = np.fft.irfft(np.fft.rfft(x[i:i + block], nfft) * H, nfft)[: len(x[i:i + block]) + n - 1]
        out[i:i + len(seg)] += seg
    return x + wet * out[: len(x)]


def _note(p: int, vel: int, hold: float) -> np.ndarray:
    f0 = 440.0 * 2 ** ((p - 69) / 12)
    L = int(min(hold + 0.5, 3.8) * SR)
    t = (np.arange(L, dtype=np.float32) / SR)[None, :]
    nstr = 1 if p < 33 else 2 if p < 48 else 3
    v = (vel / 127) ** 1.3
    base_decay = 0.5 + f0 / 900
    out = np.zeros(L, dtype=np.float32)
    B = 1e-4 * (f0 / 220) ** 2                          # inharmonicité de la corde
    ks = np.arange(1, K + 1, dtype=np.float32)[:, None]
    for s in range(nstr):
        cents = (s - (nstr - 1) / 2) * 1.6               # cordes légèrement désaccordées = son plus vivant
        f = f0 * 2 ** (cents / 1200)
        fk = ks * f * np.sqrt(1 + B * ks ** 2)
        amp = (1.0 / ks ** (1.15 - 0.5 * v)) * (fk < SR / 2.2)       # plus fort = plus brillant
        dec = base_decay * (1 + 0.55 * (ks - 1))                      # les aigus s'éteignent plus vite
        out += (amp * np.exp(-t * dec) * np.sin(2 * np.pi * fk * t)).sum(axis=0) / nstr
    n_h = int(0.012 * SR)                                # bruit de marteau
    rng = np.random.default_rng(p * 131 + vel)
    out[:n_h] += (rng.standard_normal(n_h) * np.linspace(1, 0, n_h) ** 2 * 0.07 * v).astype(np.float32)
    ti = t[0]
    out *= np.minimum(ti / 0.003, 1.0)
    out *= np.where(ti > hold, np.exp(-(ti - hold) * 9), 1.0)       # relâchement
    return out * v


def render_audio(notes, start: float, duration: float) -> np.ndarray:
    """Retourne un tableau (N, 2) stéréo flottant dans [-1, 1]."""
    n_out = int(duration * SR)
    buf = np.zeros((n_out + 4 * SR, 2), dtype=np.float32)
    for n in notes:
        if n.end <= start or n.start >= start + duration:
            continue
        t0 = n.start - start
        hold = max(min(n.end, start + duration) - max(n.start, start), 0.08)
        seg = _note(n.pitch, n.velocity, hold)
        i0 = int(t0 * SR)
        if i0 < 0:
            seg = seg[-i0:]
            i0 = 0
        pan = float(np.clip((n.pitch - 60) / 60 * 0.4, -0.45, 0.45))
        gl, gr = np.cos((pan + 0.5) * np.pi / 2), np.sin((pan + 0.5) * np.pi / 2)
        m = min(len(seg), len(buf) - i0)
        buf[i0:i0 + m, 0] += seg[:m] * gl
        buf[i0:i0 + m, 1] += seg[:m] * gr
    buf = buf[:n_out]
    if np.abs(buf).max() > 0:
        buf = np.stack([_reverb(buf[:, 0].astype(np.float64), seed=1), _reverb(buf[:, 1].astype(np.float64), seed=2)], axis=1)
        peak = np.abs(buf).max()
        buf = np.tanh(buf / peak * 1.5) / np.tanh(1.5) * 0.89           # limiteur doux
    fade = min(int(0.5 * SR), len(buf))
    buf[-fade:] *= np.linspace(1, 0, fade)[:, None]
    return buf.astype(np.float32)


def write_wav(path, audio: np.ndarray):
    a = np.clip(audio, -1, 1)
    ch = 1 if a.ndim == 1 else a.shape[1]
    with wave.open(str(path), "wb") as w:
        w.setnchannels(ch); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((a * 32767).astype("<i2").tobytes())
