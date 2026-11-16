"""Erzeugt den Start-Sound intro.wav (reines Python, kein numpy).  Version 3.

Ablauf (synchron zur Start-Animation in ui.html):
  0.00-0.95 s  Riser: Luft-Rauschen mit steigendem Filter + aufsteigender Ton (Partikel fliegen zur Mitte)
  0.95 s       Impact: tiefer Sub-Schlag + kurzer Klick + Rauschstoss (Pfeil landet, Ringwelle, Funken)
  0.95 s ->    warmer Akkord-Teppich (E-Dur add9), schwillt an und klingt lang aus
  1.15-1.45 s  vier helle Glockentoene aufsteigend, links -> rechts (Schriftzug erscheint)
  danach       Hall, sanftes Ausblenden bis zur Stille (~4.2 s)
"""
import math
import os
import random
import struct
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
SR = 44100
DUR = 4.2
N = int(SR * DUR)
IMPACT = 0.95
random.seed(11)


def add(buf_l, buf_r, start, samples, pan=0.5, gain=1.0):
    """Mono-Samples ab Zeitpunkt start (s) in Stereo-Puffer mischen (pan 0=links, 1=rechts)."""
    i0 = int(start * SR)
    gl = math.cos(pan * math.pi / 2) * gain
    gr = math.sin(pan * math.pi / 2) * gain
    for k, v in enumerate(samples):
        i = i0 + k
        if 0 <= i < N:
            buf_l[i] += v * gl
            buf_r[i] += v * gr


def env_ad(t, a, d):
    if t < 0:
        return 0.0
    if t < a:
        return math.sin(t / a * math.pi / 2) ** 2
    return math.exp(-(t - a) / d)


def riser():
    """Rauschen durch Bandpass (zwei Tiefpaesse, Differenz) mit steigender Mitte + Sinus-Sweep."""
    n = int(SR * (IMPACT + 0.05))
    out = []
    lp_a = lp_b = lp_c = 0.0
    ph = 0.0
    for i in range(n):
        t = i / SR
        x = random.uniform(-1, 1)
        prog = min(1.0, t / IMPACT)
        fc = 300 + 4200 * prog ** 2.2
        a1 = 1 - math.exp(-2 * math.pi * fc / SR)
        a2 = 1 - math.exp(-2 * math.pi * fc * 0.35 / SR)
        lp_a += a1 * (x - lp_a)
        lp_b += a1 * (lp_a - lp_b)
        lp_c += a2 * (lp_b - lp_c)
        band = lp_b - lp_c
        f = 90 * 2 ** (2.3 * prog ** 1.6)            # ~90 -> ~440 Hz
        ph += 2 * math.pi * f / SR
        tone = math.sin(ph) * 0.35 + math.sin(ph * 2) * 0.08
        vol = prog ** 2.4
        if t > IMPACT - 0.02:                           # in den Impact hinein weich auslaufen
            vol *= max(0.0, 1 - (t - (IMPACT - 0.02)) / 0.07)
        out.append((band * 1.6 + tone * 0.5) * vol)
    return out


def impact():
    n = int(SR * (DUR - IMPACT))  # bis zum Ende, sonst knackt es beim Abschneiden
    out = []
    ph_sub = ph_mid = 0.0
    lp = 0.0
    for i in range(n):
        t = i / SR
        f_sub = 38 + 34 * math.exp(-t / 0.06)
        ph_sub += 2 * math.pi * f_sub / SR
        sub = math.sin(ph_sub) * env_ad(t, 0.003, 0.32) * 1.0
        ph_mid += 2 * math.pi * (120 * math.exp(-t / 0.2) + 80) / SR
        mid = math.sin(ph_mid) * env_ad(t, 0.002, 0.07) * 0.35
        x = random.uniform(-1, 1)
        lp += 0.25 * (x - lp)
        burst = lp * env_ad(t, 0.001, 0.09) * 0.55
        click = x * env_ad(t, 0.0005, 0.004) * 0.35
        out.append(sub + mid + burst + click)
    return out


def tone(freq, dur, a, d, partials=((1, 1.0), (2, 0.28), (3, 0.08)), detune=0.0):
    n = int(SR * dur)
    out = []
    for i in range(n):
        t = i / SR
        e = env_ad(t, a, d)
        v = 0.0
        for mult, amp in partials:
            v += math.sin(2 * math.pi * (freq * mult + detune) * t) * amp
        out.append(v * e)
    return out


def bell(freq, dur=1.6):
    # Glocke: Grundton + leicht unharmonische Obertoene, schneller Einschwung
    return tone(freq, dur, 0.004, 0.45, partials=((1, 1.0), (2.756, 0.22), (5.404, 0.06)))


def reverb(buf, delays, fb, mix):
    wet = [0.0] * N
    for d in delays:
        d = int(SR * d)
        line = [0.0] * N
        damp = 0.0
        for i in range(d, N):
            damp = damp * 0.35 + line[i - d] * 0.65
            line[i] = buf[i - d] + damp * fb
        for i in range(N):
            wet[i] += line[i] / len(delays)
    for d, g in ((0.0051, 0.6), (0.0017, 0.6)):
        d = int(SR * d)
        out = [0.0] * N
        for i in range(N):
            xd = wet[i - d] if i >= d else 0.0
            yd = out[i - d] if i >= d else 0.0
            out[i] = -g * wet[i] + xd + g * yd
        wet = out
    return [b + w * mix for b, w in zip(buf, wet)]


def build():
    # Gruppen getrennt, damit jede ihren passenden Hall bekommt
    rL, rR = [0.0] * N, [0.0] * N          # Riser
    iL, iR = [0.0] * N, [0.0] * N          # Impact
    pL, pR = [0.0] * N, [0.0] * N          # Akkord + Glocken

    r = riser()
    add(rL, rR, 0.0, r, pan=0.42, gain=0.75)
    add(rL, rR, 0.0, r[200:] + [0.0] * 200, pan=0.58, gain=0.75)   # leicht versetzt = breiter

    add(iL, iR, IMPACT, impact(), pan=0.5, gain=1.0)

    # Akkord E-Dur add9 (E3 B3 E4 G#4 B4 F#5), weicher Einschwung, lang ausklingend
    chord = [(164.81, 0.20, 0.35), (246.94, 0.16, 0.65), (329.63, 0.15, 0.4),
             (415.30, 0.12, 0.6), (493.88, 0.10, 0.45), (739.99, 0.06, 0.55)]
    for f, amp, pan in chord:
        add(pL, pR, IMPACT, tone(f, DUR - IMPACT, 0.22, 1.5, detune=0.04), pan=pan, gain=amp)
    # Glocken zum Schriftzug: B5 E6 G#6 B6, links -> rechts
    for k, f in enumerate((987.77, 1318.51, 1661.22, 1975.53)):
        start = 1.15 + k * 0.1
        # bis zum Dateiende klingen lassen, sonst knackt es, wo der Ton abgeschnitten wird
        add(pL, pR, start, bell(f, DUR - start), pan=0.3 + 0.13 * k, gain=0.13 - 0.015 * k)

    pL = reverb(pL, (0.0297, 0.0371, 0.0411, 0.0437), 0.86, 0.55)
    pR = reverb(pR, (0.0313, 0.0353, 0.0427, 0.0451), 0.86, 0.55)
    iL = reverb(iL, (0.0297, 0.0411), 0.7, 0.25)
    iR = reverb(iR, (0.0313, 0.0427), 0.7, 0.25)
    rL = reverb(rL, (0.0297, 0.0371), 0.6, 0.2)
    rR = reverb(rR, (0.0313, 0.0353), 0.6, 0.2)

    L = [a + b + c for a, b, c in zip(rL, iL, pL)]
    R = [a + b + c for a, b, c in zip(rR, iR, pR)]

    # sanfter Limiter (tanh), dann Ausblenden
    peak = max(max(abs(v) for v in L), max(abs(v) for v in R)) or 1
    L = [math.tanh(v / peak * 1.3) for v in L]
    R = [math.tanh(v / peak * 1.3) for v in R]
    fade = int(SR * 1.5)
    for i in range(fade):
        g = 0.5 * (1 + math.cos(math.pi * i / fade))
        L[N - fade + i] *= g
        R[N - fade + i] *= g
    for i in range(int(SR * 0.005)):
        g = i / (SR * 0.005)
        L[i] *= g
        R[i] *= g

    peak = max(max(abs(v) for v in L), max(abs(v) for v in R)) or 1
    gain = 0.178 / peak  # -15 dB Spitze (Colin: "viel leiser"; vorher -3 dB = 4x lauter)
    path = os.path.join(HERE, "intro.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        frames = bytearray()
        for a, b in zip(L, R):
            frames += struct.pack("<hh", int(a * gain * 32767), int(b * gain * 32767))
        w.writeframes(bytes(frames))
    print("ok", path)


if __name__ == "__main__":
    build()
