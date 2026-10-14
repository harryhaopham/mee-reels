"""Royalty-free audio generated from scratch for MEE animated reels.

  python mee_reel_audio.py <out_dir> <duration> <events.json>

events.json: {"impact": [t...], "whoosh": [t...], "pop": [t...], "ding": [t...]}
Writes <out_dir>/_music.wav (light pop bed ~100 BPM, I-V-vi-IV) and <out_dir>/_sfx.wav (48 kHz stereo).
"""
import sys, os, json, wave
import numpy as np

SR = 48000
out_dir, dur = sys.argv[1], float(sys.argv[2])
ev = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else {}
N = int(SR * (dur + 0.5)); rng = np.random.default_rng(7)


def add(buf, start, sig, gain=1.0):
    i = int(max(0, start) * SR)
    if i >= len(buf): return
    sig = sig[: len(buf) - i]; buf[i:i + len(sig)] += sig * gain


def midi(m): return 440 * 2 ** ((m - 69) / 12)
def tt(sec): return np.arange(int(sec * SR)) / SR


def epiano(f, L):
    t = tt(L); env = np.exp(-t * 2.2) * np.minimum(1, t / .008)
    return (np.sin(2*np.pi*f*t) + .35*np.sin(4*np.pi*f*t)*np.exp(-t*5) + .12*np.sin(6*np.pi*f*t)*np.exp(-t*8)) * env


def pad(fs, L):
    t = tt(L); env = np.minimum(1, t / .4) * np.minimum(1, (L - t) / .4)
    return sum(np.sin(2*np.pi*f*t + i) + .5*np.sin(2*np.pi*f*1.003*t) for i, f in enumerate(fs)) * env / len(fs)


def kick():
    t = tt(.35); f = 50 + 90 * np.exp(-t * 30); return np.sin(2*np.pi*np.cumsum(f)/SR) * np.exp(-t * 9)


def hat(o=False):
    n = np.diff(np.concatenate([[0], rng.standard_normal(int(.12 * SR))])); return n * np.exp(-tt(.12)[:len(n)] * (18 if o else 60))


def clap():
    n = rng.standard_normal(int(.2 * SR)); t = tt(.2)[:len(n)]
    return np.convolve(n * np.exp(-t * 25), np.ones(6) / 6, "same")


def write(name, L, R):
    with wave.open(os.path.join(out_dir, name), "w") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(np.stack([L, R], 1), -1, 1) * 32767).astype(np.int16).tobytes())


# ---- music bed
L = np.zeros(N); R = np.zeros(N); beat = 60 / 100; bar = 4 * beat
prog = [[60, 64, 67, 71], [55, 59, 62, 67], [57, 60, 64, 67], [53, 57, 60, 64]]; bass = [36, 43, 45, 41]
t = 0.0; bi = 0
while t < dur + bar:
    ch = prog[bi % 4]
    add(L, t, pad([midi(m) for m in ch], bar), .10); add(R, t, pad([midi(m + 12) for m in ch[:2]], bar), .06)
    for off in [0, 1.5, 2, 3.5]:
        for j, m in enumerate(ch):
            s = epiano(midi(m), 1.2); add(L, t + off*beat + j*.006, s, .055); add(R, t + off*beat + j*.006, s, .05)
    for off in [0, 1.5, 2.5]:
        b = epiano(midi(bass[bi % 4]), .6); add(L, t + off*beat, b, .16); add(R, t + off*beat, b, .16)
    for k in range(4):
        if k in (0, 2): add(L, t + k*beat, kick(), .32); add(R, t + k*beat, kick(), .32)
        else: c = clap(); add(L, t + k*beat, c, .07); add(R, t + k*beat, c, .07)
    for k in range(8):
        h = hat(k % 4 == 3); g = .05 if k % 2 else .03
        add(L, t + k*beat/2, h, g*.8); add(R, t + k*beat/2, h, g)
    t += bar; bi += 1
tm = np.arange(N) / SR; fade = np.minimum(1, tm / 0.6) * np.clip((dur + .2 - tm) / 1.5, 0, 1)
L *= fade; R *= fade; m = max(np.abs(L).max(), np.abs(R).max()); write("_music.wav", L / m * .8, R / m * .8)

# ---- sfx
FL = np.zeros(N); FR = np.zeros(N)
for t0 in ev.get("impact", []):
    t = tt(1.2); f = 40 + 120 * np.exp(-t * 18)
    boom = np.sin(2*np.pi*np.cumsum(f)/SR) * np.exp(-t * 3.5)
    crack = np.convolve(rng.standard_normal(len(t)) * np.exp(-t * 28), np.ones(3) / 3, "same")
    hit = np.tanh(1.6 * (boom * .9 + crack * .45)); hit /= np.abs(hit).max()
    add(FL, t0, hit, .9); add(FR, t0, hit, .9)
for c in ev.get("whoosh", []):
    d = .6; n = int(d * SR); x = rng.standard_normal(n); tw = np.arange(n) / SR
    env = np.exp(-((tw - d * .55) / .13) ** 2); fc = 400 + 3500 * env; out = np.zeros(n); y1 = y2 = 0.0
    for i in range(n):
        f_ = 2 * np.sin(np.pi * fc[i] / SR); hp = x[i] - y2 - .35 * y1; y1 += f_ * hp; y2 += f_ * y1; out[i] = y1
    out = out * env / np.abs(out * env).max(); pan = np.linspace(-1, 1, n)
    add(FL, c - d * .55, out * (1 - pan) / 2, .5); add(FR, c - d * .55, out * (1 + pan) / 2, .5)
for t0 in ev.get("pop", []):
    t = tt(.12); f = 900 * np.exp(-t * 12) + 300
    s = np.sin(2*np.pi*np.cumsum(f)/SR) * np.exp(-t * 35)
    add(FL, t0, s, .35); add(FR, t0, s, .35)
for t0 in ev.get("ding", []):
    t = tt(.9)
    s = (np.sin(2*np.pi*1318.5*t) + .6*np.sin(2*np.pi*1975.5*t)) * np.exp(-t * 5) * np.minimum(1, t / .003)
    add(FL, t0, s, .28); add(FR, t0, s, .28)
write("_sfx.wav", FL, FR)
print("audio ok")
