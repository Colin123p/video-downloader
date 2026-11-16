"""Erzeugt den Start-Sound intro.wav (reines Python, kein numpy).  Version 4 ("produziert").

Ziel: klingt wie ein von Hand produziertes App-Intro, nicht wie Test-Sinustoene.
Dafuer echte Studio-Verfahren statt nackter Sinuswellen:
  * FM-E-Piano (wie Rhodes/DX7): Ton mit "Tine"-Anschlag und Klang, der beim Abklingen weicher wird
  * Harfen-artiges Pluck (FM mit schnell schliessendem Obertongehalt) fuer die Arpeggio-Noten
  * warmer Pad aus verstimmten Saegezaehnen durch ein sich oeffnendes Resonanzfilter
  * Reverse-Swell: der Hall des Akkords rueckwaerts abgespielt, schwillt bis zum Aufprall an
  * Rosa Rauschen durch Bandpass-Sweep (RBJ-Biquad) als Luft-Whoosh, links/rechts entkoppelt
  * weicher Sub-Impact mit Tonhoehen-Abfall und leichter Saettigung
  * Freeverb (8 Kammfilter + 4 Allpaesse je Kanal) statt metallischem Mini-Hall
  * "menschliche" Ungenauigkeit: leicht versetzte Anschlaege, unterschiedliche Anschlagstaerke
  * Master: Hochpass, sanfter Kompressor, Soft-Clip, -15 dB Spitze, weiches Ausblenden

Zeitplan (passend zur Start-Animation in ui.html):
  0.00-0.95 s  Reverse-Swell + Whoosh (Partikel fliegen zur Mitte)
  0.95 s       Impact + E-Piano-Akkord Emaj9 + Pad (Pfeil landet)
  1.15-1.45 s  Pluck-Arpeggio E5 G#5 B5 D#6, links -> rechts (Schriftzug)
  danach       Hall, Ausklang bis ~3.8 s
"""
import math
import os
import random
import struct
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
SR = 44100
DUR = 3.8
N = int(SR * DUR)
IMPACT = 0.95
TAU = 2 * math.pi
rng = random.Random(20261116)


# ------------------------------------------------------------------ Bausteine
class Biquad:
    """RBJ-Audio-EQ-Cookbook-Filter (lowpass / highpass / bandpass), Koeffizienten aenderbar."""

    def __init__(self, kind, fc, q=0.707):
        self.kind = kind
        self.x1 = self.x2 = self.y1 = self.y2 = 0.0
        self.set(fc, q)

    def set(self, fc, q=0.707):
        fc = max(10.0, min(fc, SR * 0.45))
        w = TAU * fc / SR
        cw, sw = math.cos(w), math.sin(w)
        a = sw / (2 * q)
        if self.kind == "lp":
            b0, b1, b2 = (1 - cw) / 2, 1 - cw, (1 - cw) / 2
        elif self.kind == "hp":
            b0, b1, b2 = (1 + cw) / 2, -(1 + cw), (1 + cw) / 2
        else:  # bandpass, 0 dB Spitze
            b0, b1, b2 = a, 0.0, -a
        a0, a1, a2 = 1 + a, -2 * cw, 1 - a
        self.b0, self.b1, self.b2, self.a1, self.a2 = b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0

    def __call__(self, x):
        y = self.b0 * x + self.b1 * self.x1 + self.b2 * self.x2 - self.a1 * self.y1 - self.a2 * self.y2
        self.x2, self.x1, self.y2, self.y1 = self.x1, x, self.y1, y
        return y


class Pink:
    """Rosa Rauschen (Paul Kellet) - klingt natuerlicher als weisses Rauschen."""

    def __init__(self, seed):
        self.r = random.Random(seed)
        self.b = [0.0] * 7

    def __call__(self):
        w = self.r.uniform(-1, 1)
        b = self.b
        b[0] = 0.99886 * b[0] + w * 0.0555179
        b[1] = 0.99332 * b[1] + w * 0.0750759
        b[2] = 0.96900 * b[2] + w * 0.1538520
        b[3] = 0.86650 * b[3] + w * 0.3104856
        b[4] = 0.55000 * b[4] + w * 0.5329522
        b[5] = -0.7616 * b[5] - w * 0.0168980
        out = b[0] + b[1] + b[2] + b[3] + b[4] + b[5] + b[6] + w * 0.5362
        b[6] = w * 0.115926
        return out * 0.11


def buf():
    return [0.0] * N


def place(L, R, start, mono=None, left=None, right=None, pan=0.5, gain=1.0):
    """Mono (mit Panorama) oder Stereo-Signal ab start (s) in L/R mischen."""
    i0 = int(round(start * SR))
    if mono is not None:
        gl = math.cos(pan * math.pi / 2) * gain
        gr = math.sin(pan * math.pi / 2) * gain
        for k, v in enumerate(mono):
            i = i0 + k
            if 0 <= i < N:
                L[i] += v * gl
                R[i] += v * gr
    else:
        for k in range(len(left)):
            i = i0 + k
            if 0 <= i < N:
                L[i] += left[k] * gain
                R[i] += right[k] * gain


def note_hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


# ------------------------------------------------------------------ Instrumente
def epiano(freq, dur, vel=1.0):
    """2-Operator-FM-E-Piano: Koerper (1:1, Index faellt) + Tine-Anschlag (1:14, sehr kurz)."""
    n = int(dur * SR)
    out = [0.0] * n
    pc = pm = pt = ptm = 0.0
    det = rng.uniform(-0.6, 0.6)                 # minimale Verstimmung pro Note, wie echtes Instrument
    f = freq * 2 ** (det / 1200)
    for i in range(n):
        t = i / SR
        att = min(1.0, t / 0.004)
        amp = att * (0.72 * math.exp(-t / 1.25) + 0.28 * math.exp(-t / 0.22)) * vel
        idx = (0.4 + 1.9 * vel * math.exp(-t / 0.55))
        pm += TAU * f / SR
        pc += TAU * f / SR
        body = math.sin(pc + idx * math.sin(pm))
        ptm += TAU * f * 14 / SR
        pt += TAU * f / SR
        tine = math.sin(pt + 1.3 * math.sin(ptm)) * math.exp(-t / 0.035) * 0.35 * vel
        out[i] = (body + tine) * amp
    return out


def pluck(freq, dur, vel=1.0):
    """Harfen-/Pluck-Ton: FM 1:2 mit schnell sinkendem Index = heller Anschlag, weicher Ausklang."""
    n = int(dur * SR)
    out = [0.0] * n
    pc = pm = 0.0
    for i in range(n):
        t = i / SR
        att = min(1.0, t / 0.002)
        amp = att * math.exp(-t / 0.75) * vel
        idx = 2.4 * math.exp(-t / 0.06) + 0.25
        pm += TAU * freq * 2 / SR
        pc += TAU * freq / SR
        out[i] = math.sin(pc + idx * math.sin(pm)) * amp
    return out


def saw_partials(freq, n_harm):
    lim = int((SR * 0.45) // freq)
    return [(h, 1.0 / h) for h in range(1, min(n_harm, lim) + 1)]


def pad(freqs, dur):
    """Warmer Pad: je Note zwei verstimmte Saegezaehne (additiv, ohne Aliasing), Filter oeffnet sich."""
    n = int(dur * SR)
    L, R = [0.0] * n, [0.0] * n
    fl, fr = Biquad("lp", 300, 0.9), Biquad("lp", 300, 0.9)
    phases = []
    for f in freqs:
        for cents, side in ((-7, 0), (7, 1)):
            ff = f * 2 ** (cents / 1200)
            phases.append([ff, side, rng.uniform(0, TAU), saw_partials(ff, 14)])
    for i in range(n):
        t = i / SR
        if i % 32 == 0:
            fc = 300 + 2100 * (1 - math.exp(-t / 0.45))
            fl.set(fc, 0.9)
            fr.set(fc, 0.9)
        l = r = 0.0
        for p in phases:
            ff, side, ph0, parts = p
            ph = ph0 + TAU * ff * t
            v = 0.0
            for h, a in parts:
                v += math.sin(h * ph) * a
            if side == 0:
                l += v
            else:
                r += v
        env = (1 - math.exp(-t / 0.35)) * math.exp(-t / 1.6)
        L[i] = fl(l) * env
        R[i] = fr(r) * env
    return L, R


def whoosh(dur):
    """Rosa Rauschen durch Bandpass-Sweep, L/R aus getrennten Quellen (breit, nicht mono)."""
    n = int(dur * SR)
    outs = []
    for seed, drift in ((11, 1.00), (12, 1.07)):
        src = Pink(seed)
        bp = Biquad("bp", 300, 1.1)
        hp = Biquad("hp", 120, 0.7)
        o = [0.0] * n
        for i in range(n):
            t = i / SR
            if i % 16 == 0:
                k = min(1.0, t / IMPACT)
                bp.set((260 * (4200 / 260) ** (k ** 1.5)) * drift, 1.1)
            if t < IMPACT:
                env = (t / IMPACT) ** 2.6
            else:
                env = math.exp(-(t - IMPACT) / 0.11)
            o[i] = hp(bp(src())) * env * 3.2
        outs.append(o)
    return outs[0], outs[1]


def impact(dur):
    n = int(dur * SR)
    out = [0.0] * n
    ph = 0.0
    lp = Biquad("lp", 900, 0.7)
    src = Pink(99)
    for i in range(n):
        t = i / SR
        f = 41 + 46 * math.exp(-t / 0.045)
        ph += TAU * f / SR
        body = math.sin(ph) * min(1.0, t / 0.002) * math.exp(-t / 0.30)
        thump = lp(src()) * 6 * math.exp(-t / 0.035)
        out[i] = math.tanh((body * 1.15 + thump) * 1.4) / 1.4
    return out


# ------------------------------------------------------------------ Freeverb
class Freeverb:
    COMBS = (1116, 1188, 1277, 1356, 1422, 1491, 1557, 1617)
    ALLP = (556, 441, 341, 225)

    def __init__(self, room=0.84, damp=0.32, spread=23):
        self.ch = []
        for off in (0, spread):   # rechter Kanal leicht andere Laengen = breites Stereo
            combs = [[[0.0] * (d + off), 0, 0.0] for d in self.COMBS]
            alls = [[[0.0] * (d + off), 0] for d in self.ALLP]
            self.ch.append((combs, alls))
        self.fb = room
        self.damp = damp

    def process(self, L, R):
        outs = []
        for c, x in zip(self.ch, (L, R)):
            combs, alls = c
            y = [0.0] * N
            fb, d1, d2 = self.fb, self.damp, 1 - self.damp
            for i in range(N):
                inp = x[i] * 0.015
                acc = 0.0
                for cb in combs:
                    line, idx, store = cb
                    o = line[idx]
                    store = o * d2 + store * d1
                    cb[2] = store
                    line[idx] = inp + store * fb
                    cb[1] = idx + 1 if idx + 1 < len(line) else 0
                    acc += o
                for ap in alls:
                    line, idx = ap
                    bo = line[idx]
                    line[idx] = acc + bo * 0.5
                    acc = bo - acc
                    ap[1] = idx + 1 if idx + 1 < len(line) else 0
                y[i] = acc
            outs.append(y)
        return outs


# ------------------------------------------------------------------ Mix
def build():
    DL, DR = buf(), buf()          # trocken
    SL, SR_ = buf(), buf()         # Hall-Send

    # Akkord Emaj9: E2 | B3 D#4 F#4 G#4 | (Bass + E-Piano), leicht "geschrammt" wie von Hand
    chord = [(40, 0.55, 0.50, 0.000), (59, 0.62, 0.38, 0.010), (63, 0.55, 0.62, 0.017),
             (66, 0.50, 0.45, 0.024), (68, 0.48, 0.58, 0.031)]
    for midi, vel, pan, delay in chord:
        v = vel * rng.uniform(0.92, 1.0)
        tone = epiano(note_hz(midi), DUR - IMPACT - delay, v)
        place(DL, DR, IMPACT + delay, mono=tone, pan=pan, gain=0.30)
        place(SL, SR_, IMPACT + delay, mono=tone, pan=pan, gain=0.22)

    # Pad (E3 B3 G#4), sehr leise darunter
    pl, pr = pad([note_hz(52), note_hz(59), note_hz(68)], DUR - IMPACT)
    place(DL, DR, IMPACT, left=pl, right=pr, gain=0.020)
    place(SL, SR_, IMPACT, left=pl, right=pr, gain=0.018)

    # Pluck-Arpeggio E5 G#5 B5 D#6, links -> rechts, minimal ungenau wie gespielt
    for k, midi in enumerate((76, 80, 83, 87)):
        start = 1.15 + k * 0.10 + rng.uniform(-0.006, 0.006)
        vel = (0.85, 0.75, 0.80, 0.70)[k] * rng.uniform(0.93, 1.0)
        tone = pluck(note_hz(midi), DUR - start, vel)
        place(DL, DR, start, mono=tone, pan=0.28 + 0.15 * k, gain=0.16)
        place(SL, SR_, start, mono=tone, pan=0.28 + 0.15 * k, gain=0.20)

    # Impact
    imp = impact(DUR - IMPACT)
    place(DL, DR, IMPACT, mono=imp, pan=0.5, gain=0.55)
    place(SL, SR_, IMPACT, mono=imp, pan=0.5, gain=0.08)

    # Whoosh (Stereo)
    wl, wr = whoosh(IMPACT + 0.8)
    place(DL, DR, 0.0, left=wl, right=wr, gain=0.32)
    place(SL, SR_, 0.0, left=wl, right=wr, gain=0.10)

    # Hall
    WL, WR = Freeverb().process(SL, SR_)

    # Reverse-Swell: Hall des Akkords rueckwaerts, endet genau am Aufprall
    swell_len = int(0.9 * SR)
    seg_l = WL[int(IMPACT * SR):int(IMPACT * SR) + swell_len][::-1]
    seg_r = WR[int(IMPACT * SR):int(IMPACT * SR) + swell_len][::-1]
    for k in range(swell_len):
        x = k / swell_len
        g = x ** 1.6 * (1 - max(0.0, (x - 0.97) / 0.03))   # ganz am Ende kurz absetzen
        seg_l[k] *= g
        seg_r[k] *= g
    swell_start = IMPACT - swell_len / SR

    L = [d + w * 1.0 for d, w in zip(DL, WL)]
    R = [d + w * 1.0 for d, w in zip(DR, WR)]
    place(L, R, swell_start, left=seg_l, right=seg_r, gain=0.9)

    # ---------------- Master
    hl, hr = Biquad("hp", 28, 0.7), Biquad("hp", 28, 0.7)
    L = [hl(v) for v in L]
    R = [hr(v) for v in R]
    peak = max(max(abs(v) for v in L), max(abs(v) for v in R)) or 1.0
    L = [v / peak for v in L]
    R = [v / peak for v in R]
    # sanfter Kompressor (RMS, 2:1 ab -14 dB) fuer "zusammengeklebten" Klang
    env = 0.0
    a_att, a_rel = math.exp(-1 / (0.008 * SR)), math.exp(-1 / (0.180 * SR))
    thr = 10 ** (-14 / 20)
    for i in range(N):
        lvl = max(abs(L[i]), abs(R[i]))
        env = a_att * env + (1 - a_att) * lvl if lvl > env else a_rel * env + (1 - a_rel) * lvl
        g = 1.0 if env <= thr else (thr * (env / thr) ** 0.5) / env
        L[i] = math.tanh(L[i] * g * 1.6) / 1.6
        R[i] = math.tanh(R[i] * g * 1.6) / 1.6

    fade = int(SR * 1.3)
    for i in range(fade):
        g = 0.5 * (1 + math.cos(math.pi * i / fade))
        L[N - fade + i] *= g
        R[N - fade + i] *= g
    for i in range(int(SR * 0.005)):
        g = i / (SR * 0.005)
        L[i] *= g
        R[i] *= g

    peak = max(max(abs(v) for v in L), max(abs(v) for v in R)) or 1
    gain = 0.178 / peak  # -15 dB Spitze (Colin: "viel leiser")
    path = os.path.join(HERE, "intro.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        frames = bytearray()
        for a, b in zip(L, R):
            # minimales Dither gegen Quantisierungsrauschen im leisen Ausklang
            da = (rng.random() - rng.random()) / 32768
            db = (rng.random() - rng.random()) / 32768
            frames += struct.pack("<hh", int(round((a * gain + da) * 32767)), int(round((b * gain + db) * 32767)))
        w.writeframes(bytes(frames))
    print("ok", path)


if __name__ == "__main__":
    build()
