"""Son du piano. Sur Mac : le piano du système (synthétiseur General MIDI d'Apple, via `afconvert`), bien plus réaliste ; velocités adoucies, pédale
de sustain automatique, réverbération légère. Sinon (ou si afconvert échoue) : piano de secours en numpy — cordes désaccordées, 20 harmoniques à
deux phases d'extinction (attaque rapide puis résonance), bruit de marteau, stéréo selon la hauteur, réverbération avec premières réflexions, filtrage doux."""
import shutil
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

SR = 44100
K = 20                         # nombre d'harmoniques (8 donnait un son fin, « électronique »)


def _reverb(x: np.ndarray, wet=0.17, seconds=1.1, seed=0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    ir = rng.standard_normal(n) * np.exp(-np.arange(n) / SR / 0.32)
    ir = np.convolve(ir, np.ones(4) / 4, mode="same")                  # queue filtrée : chaude, pas sifflante
    for d, g in ((0.011, 0.55), (0.019, 0.45), (0.029, 0.35), (0.043, 0.25)):   # premières réflexions : sensation de pièce
        ir[int(d * SR)] += g * np.abs(ir).max() * 3
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
    L = int(min(hold + 0.7, 4.5) * SR)
    t = (np.arange(L, dtype=np.float32) / SR)[None, :]
    nstr = 1 if p < 33 else 2 if p < 48 else 3
    v = (vel / 127) ** 1.25
    out = np.zeros(L, dtype=np.float32)
    B = 1.2e-4 * (f0 / 220) ** 2                          # inharmonicité de la corde
    ks = np.arange(1, K + 1, dtype=np.float32)[:, None]
    low = np.clip((84 - p) / 60, 0.0, 1.0)                 # graves : plus longs et plus riches ; aigus : brefs et purs
    d_fast = (1.6 + f0 / 500) * (1 + 0.35 * (ks - 1))      # extinction rapide (attaque)
    d_slow = (0.28 + f0 / 1800) * (1 + 0.12 * (ks - 1))     # résonance longue (« after-sound » du piano)
    tilt = 1.25 - 0.55 * v + 0.35 * (1 - low)               # forte frappe = plus brillant
    for s in range(nstr):
        cents = (s - (nstr - 1) / 2) * 2.2                  # cordes légèrement désaccordées : battements vivants
        f = f0 * 2 ** (cents / 1200)
        fk = ks * f * np.sqrt(1 + B * ks ** 2)
        amp = (1.0 / ks ** tilt) * (fk < SR / 2.3)
        env = 0.62 * np.exp(-t * d_fast) + 0.38 * np.exp(-t * d_slow)
        ph = (s * 0.7 + ks * 0.37)
        out += (amp * env * np.sin(2 * np.pi * fk * t + ph)).sum(axis=0) / nstr
    n_h = int(0.016 * SR)                                # bruit de marteau (filtré : sourd, pas sifflant)
    rng = np.random.default_rng(p * 131 + vel)
    nz = rng.standard_normal(n_h)
    nz = np.convolve(nz, np.ones(5) / 5, mode="same")
    out[:n_h] += (nz * np.linspace(1, 0, n_h) ** 2 * 0.06 * v).astype(np.float32)
    ti = t[0]
    out *= np.minimum(ti / 0.004, 1.0)                    # attaque très courte
    rel = 5.0 + 6.0 * (1 - low)                           # relâchement : pédale douce, plus court dans l'aigu
    out *= np.where(ti > hold, np.exp(-(ti - hold) * rel), 1.0)
    return out * v


def _eq(x: np.ndarray) -> np.ndarray:
    """Filtre doux : coupe les infra-graves (< 35 Hz) et adoucit l'extrême aigu (> 9 kHz) pour éviter un son dur ou métallique."""
    n = len(x)
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    g = np.clip(f / 40.0, 0, 1) ** 4 * (1.0 / (1.0 + (f / 9000.0) ** 2) ** 0.7)
    return np.fft.irfft(X * g, n)


def render_system(notes, start: float, duration: float, run=subprocess.run) -> np.ndarray | None:
    """Piano du système macOS via `afconvert` (MIDI -> WAV). Retourne None si indisponible : l'appelant bascule alors sur le piano numpy."""
    afc = shutil.which("afconvert")
    if not afc or not (sys.platform == "darwin" or run is not subprocess.run):
        return None
    from app.midi_analyzer.writer import make_midi
    ev = []
    for n in notes:
        if n.end <= start or n.start >= start + duration:
            continue
        s0 = max(n.start, start) - start
        d = max(min(n.end, start + duration) - max(n.start, start), 0.06)
        vel = int(np.clip(50 + 0.5 * n.velocity, 40, 112))             # velocités adoucies : ni timides ni agressives
        ev.append((s0 * 2.0, d * 2.0, n.pitch, vel))                    # 120 BPM : 1 seconde = 2 temps
    if not ev:
        return None
    try:
        with tempfile.TemporaryDirectory() as td:
            mid, wav = Path(td) / "a.mid", Path(td) / "a.wav"
            mid.write_bytes(_with_pedal(make_midi(ev, bpm=120), ev))
            r = run([afc, "-f", "WAVE", "-d", "LEI16@44100", str(mid), str(wav)], capture_output=True, text=True, timeout=180)
            if getattr(r, "returncode", 1) or not wav.exists():
                return None
            with wave.open(str(wav), "rb") as w:
                ch, sw, sr = w.getnchannels(), w.getsampwidth(), w.getframerate()
                raw = w.readframes(w.getnframes())
        if sw != 2:
            return None
        a = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
        a = a.reshape(-1, ch)
        if ch == 1:
            a = np.repeat(a, 2, axis=1)
        if sr != SR:                                                     # rééchantillonnage simple (afconvert sort normalement du 44,1 kHz)
            idx = np.linspace(0, len(a) - 1, int(len(a) * SR / sr))
            a = np.stack([np.interp(idx, np.arange(len(a)), a[:, c]) for c in (0, 1)], axis=1).astype(np.float32)
        if len(a) < 0.4 * duration * SR:                                 # sortie anormalement courte : on ne s'y fie pas
            return None
        return a
    except Exception:
        return None


def _with_pedal(midi: bytes, ev) -> bytes:
    """Ajoute une pédale de sustain automatique (CC64) : enfoncée, relâchée un instant toutes les ~2,2 s et à chaque silence franc : le piano « chante »
    sans brouiller les harmonies. Réécrit le fichier MIDI avec ces événements."""
    import struct
    from app.midi_analyzer.writer import vlq
    ppq = 480
    items = []
    for s, d, p, v in ev:
        items.append((int(s * ppq), 1, 0x90, p, v)); items.append((int((s + d) * ppq), 0, 0x80, p, 0))
    end = max((int((s + d) * ppq) for s, d, _, _ in ev), default=0)
    step = int(2.2 * 2 * ppq)                                            # 2,2 s à 120 BPM
    t = 0
    items.append((0, 2, 0xB0, 64, 127))
    while t + step < end:
        t += step
        items.append((t - 40, 2, 0xB0, 64, 0)); items.append((t + 20, 3, 0xB0, 64, 127))   # petit « lever de pédale »
    items.append((end + 480, 2, 0xB0, 64, 0))
    items.sort()
    tempo = b"\x00\xff\x51\x03" + int(60e6 / 120).to_bytes(3, "big")
    body, last = tempo, 0
    for tt, _, st, a, b in items:
        body += vlq(tt - last) + bytes([st, a, b]); last = tt
    body += b"\x00\xff\x2f\x00"
    return b"MThd" + struct.pack(">IHHH", 6, 0, 1, ppq) + b"MTrk" + struct.pack(">I", len(body)) + body


def onset_lag(audio: np.ndarray, notes, start: float, duration: float, max_lag: float = 0.6, hop: int = 220):
    """Décalage mesuré entre le son et les notes (en secondes, > 0 = son en retard) et confiance (0-1).
    Compare les attaques détectées dans l'audio aux débuts de notes attendus : corrélation sur ±max_lag."""
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    n = len(mono) // hop
    if n < 20:
        return 0.0, 0.0
    e = np.sqrt((mono[:n * hop].reshape(n, hop).astype(np.float64) ** 2).mean(axis=1))
    flux = np.maximum(np.diff(e, prepend=e[0]), 0)
    exp = np.zeros(n)
    for nt in notes:
        k = int((nt.start - start) * SR / hop)
        if 0 <= k < n:
            exp[k] += nt.velocity / 127
    if flux.sum() <= 1e-9 or exp.sum() <= 0:
        return 0.0, 0.0
    sm = np.array([0.25, 0.5, 0.25])
    flux, exp = np.convolve(flux, sm, "same"), np.convolve(exp, sm, "same")
    lags = range(-int(max_lag * SR / hop), int(max_lag * SR / hop) + 1)
    corr = np.array([float((exp[max(0, -L):n - max(L, 0)] * flux[max(L, 0):n + min(L, 0)]).sum()) for L in lags])
    best = int(corr.argmax())
    conf = float((corr[best] - np.median(corr)) / (corr[best] + 1e-12))
    return list(lags)[best] * hop / SR, conf


def align_audio(audio: np.ndarray, notes, start: float, duration: float, log=None) -> np.ndarray:
    """Recale le son sur les notes quand le synthétiseur du système introduit un décalage (silence de départ, latence) : image et son restent synchrones."""
    lag, conf = onset_lag(audio, notes, start, duration)
    if conf < 0.35 or abs(lag) < 0.012:
        return audio
    k = int(round(abs(lag) * SR))
    if log:
        log(f"Son recalé de {lag * 1000:+.0f} ms pour rester synchrone avec les notes")
    if lag > 0:
        return np.concatenate([audio[k:], np.zeros((k,) + audio.shape[1:], dtype=audio.dtype)])
    return np.concatenate([np.zeros((k,) + audio.shape[1:], dtype=audio.dtype), audio])[:len(audio)]


def render_audio(notes, start: float, duration: float) -> np.ndarray:
    """Retourne un tableau (N, 2) stéréo flottant dans [-1, 1] : piano du système sur Mac, sinon piano numpy."""
    n_out = int(duration * SR)
    sysaud = render_system(notes, start, duration)
    if sysaud is not None:
        import logging
        sysaud = align_audio(sysaud, notes, start, duration, logging.getLogger(__name__).info)
    if sysaud is not None:
        buf = sysaud[:n_out]
        if len(buf) < n_out:
            buf = np.vstack([buf, np.zeros((n_out - len(buf), 2), dtype=np.float32)])
        buf = np.stack([_reverb(buf[:, 0].astype(np.float64), wet=0.10, seed=1), _reverb(buf[:, 1].astype(np.float64), wet=0.10, seed=2)], axis=1)
        peak = float(np.abs(buf).max())
        if peak > 0:
            buf = buf / peak * 0.89
        fade = min(int(0.5 * SR), len(buf))
        buf[-fade:] *= np.linspace(1, 0, fade)[:, None]
        return buf.astype(np.float32)
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
        buf = np.stack([_eq(buf[:, 0]), _eq(buf[:, 1])], axis=1)                    # filtre doux APRÈS la réverbération
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
