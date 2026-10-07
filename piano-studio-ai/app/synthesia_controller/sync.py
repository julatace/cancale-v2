"""Calage audio/image : repère l'instant où la première touche du clavier s'allume dans la capture."""
import subprocess

import numpy as np


def detect_first_note(capture, crop, trim: float, window=25.0, fps=10, keyboard_fraction=0.18, run=subprocess.run):
    """Retourne le temps (s, relatif à `trim`) de la première touche pressée, ou None.
    Le clavier occupe le bas de la fenêtre ; il est immobile tant qu'aucune touche n'est jouée."""
    c = ""
    if crop:
        c = f"crop=iw*{crop[2]:.4f}:ih*{crop[3]:.4f}:iw*{crop[0]:.4f}:ih*{crop[1]:.4f},"
    h = 400
    r = run(["ffmpeg", "-v", "error", "-ss", str(trim), "-t", str(window), "-i", str(capture),
             "-vf", f"{c}fps={fps},scale=240:{h}", "-f", "rawvideo", "-pix_fmt", "gray", "-"], capture_output=True)
    data = r.stdout
    n = len(data) // (240 * h)
    if n < 6:
        return None
    frames = np.frombuffer(data[: n * 240 * h], np.uint8).reshape(n, h, 240).astype(float)
    strip = frames[:, int(h * (1 - keyboard_fraction)):, :]
    base = strip[:3].mean(axis=0)
    diff = np.abs(strip - base).mean(axis=(1, 2))
    noise = diff[:3].max() + 1.0
    hit = np.where(diff > max(noise * 2.5, 3.0))[0]
    return float(hit[0] / fps) if len(hit) else None
