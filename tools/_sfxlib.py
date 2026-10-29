"""音效合成库(纯 numpy):呼啸 whoosh、重音 thump、滴答 tick、键帽 keytap、弹出 pop、提示音 chime、闪光 shimmer、掠过 swish。"""
import numpy as np, wave, subprocess, os, sys
SR = 44100
HERE = os.path.dirname(os.path.abspath(__file__))
rng = np.random.RandomState(11)

def add(buf, t, sig, gain=1.0, pan=0.0):
    i = int(t * SR); sig = np.asarray(sig, np.float32)
    if sig.ndim == 1: sig = np.stack([sig * (1 - max(0, pan)), sig * (1 + min(0, pan))], 1) * gain
    if i < 0 or i >= len(buf): return
    j = min(len(buf), i + len(sig)); buf[i:j] += sig[:j - i]

def env(n, a, r, curve=2.0):
    t = np.arange(n) / SR; e = np.minimum(t / max(a, 1e-4), 1.0) * np.exp(-t * curve / max(r, 1e-3)); return e.astype(np.float32)

def lowpass_sweep(x, f0, f1, peak=0.5):
    n = len(x); out = np.zeros(n, np.float32); y = 0.0
    p = np.arange(n) / n; fc = np.where(p < peak, f0 + (f1 - f0) * (p / peak) ** 1.5, f1 + (f0 - f1) * ((p - peak) / (1 - peak)) ** 1.2)
    a = 1 - np.exp(-2 * np.pi * fc / SR)
    for i in range(n): y += a[i] * (x[i] - y); out[i] = y
    return out

def whoosh(dur, bright=1.0):
    n = int(dur * SR); x = rng.normal(0, 1, n).astype(np.float32)
    y = lowpass_sweep(x, 300 * bright, 5200 * bright, 0.55)
    y2 = y - lowpass_sweep(x, 120, 600, 0.55) * 0.9           # 去掉低频,留下"气流"
    t = np.arange(n) / n; e = np.sin(np.pi * np.clip(t, 0, 1) ** 0.8) ** 2
    out = y2 * e; out /= max(1e-6, np.abs(out).max()); return out * 0.9

def thump(f0=95, dur=0.38, click=0.4):
    n = int(dur * SR); t = np.arange(n) / SR; f = f0 * np.exp(-t * 7) + 38
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)
    c = rng.normal(0, 1, n) * np.exp(-t * 220) * click
    return (s + c).astype(np.float32)

def tick(f=2600, dur=0.05, tone=0.5):
    n = int(dur * SR); t = np.arange(n) / SR
    c = rng.normal(0, 1, n) * np.exp(-t * 160)
    c = c - np.concatenate([[0], c[:-1]]) * 0.9
    s = np.sin(2 * np.pi * f * t) * np.exp(-t * 90) * tone
    return ((c * 0.5 + s)).astype(np.float32)

def keytap(depth=1.0):
    n = int(0.11 * SR); t = np.arange(n) / SR
    low = np.sin(2 * np.pi * 170 * t) * np.exp(-t * 55) * 0.8 * depth
    hi = (rng.normal(0, 1, n) * np.exp(-t * 180)); hi = hi - np.concatenate([[0], hi[:-1]]) * 0.85
    return (low + hi * 0.45).astype(np.float32)

def pop(f0=420, f1=900, dur=0.09, gain=1.0):
    n = int(dur * SR); t = np.arange(n) / SR; f = f0 + (f1 - f0) * np.minimum(t / dur * 2, 1)
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 38) * gain).astype(np.float32)

def chime(f=1318, dur=0.9):
    n = int(dur * SR); t = np.arange(n) / SR
    s = np.sin(2 * np.pi * f * t) * np.exp(-t * 5) + 0.5 * np.sin(2 * np.pi * f * 1.5 * t) * np.exp(-t * 6.5) + 0.25 * np.sin(2 * np.pi * f * 2.01 * t) * np.exp(-t * 9)
    return (s * np.minimum(t / 0.004, 1)).astype(np.float32) * 0.6

def shimmer(dur=1.2, base=2200):
    n = int(dur * SR); t = np.arange(n) / SR; s = np.zeros(n, np.float32)
    for k in range(14):
        f = base * (1 + rng.uniform(0, 1.8)); ph = rng.uniform(0, 6.28); d = rng.uniform(2.5, 6)
        s += (np.sin(2 * np.pi * f * t + ph) * np.exp(-t * d) * (1 / 14)).astype(np.float32)
    return s * np.minimum(t / 0.01, 1) * 0.8

def swish(dur=0.28):
    n = int(dur * SR); x = rng.normal(0, 1, n).astype(np.float32)
    y = lowpass_sweep(x, 1500, 7000, 0.7); t = np.arange(n) / n; return y * np.sin(np.pi * t) ** 1.5 * 0.7

