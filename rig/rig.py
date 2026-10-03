"""
Live guitar rig: Squier -> Focusrite -> Python -> headphones/monitors.

Keys (in this window):
  1  SRV        Tube Screamer into a cranked Fender, spring reverb
  2  Hendrix    Fuzz Face + Uni-Vibe into a Marshall stack
  3  Clapton    Cream-era "woman tone" (neck pickup, tone knob rolled off)
  4  Slowhand   80s Clapton Strat: mid-boost, compressed, chorus
  0  Clean      Fender clean
  t      tuner on/off (mutes the output while tuning)
  n      next tuning: Standard, Eb (SRV/Hendrix), Drop D, Open G, Open E, Open D, DADGAD,
         D Standard, Chromatic
  s      scale trainer: next scale (maqams, ragas, Japanese, gamelan...). Prints a fretboard map,
         then shows live which scale note you're on and whether your quarter-tone bends land
  r      scale trainer: next root note
  [ / ]  input trim -/+ 3 dB (more = more drive)
  - / +  master volume -/+ 3 dB
  i      swap input channel (auto-detected at startup by strumming)
  m      mute / unmute  (hit this if it ever starts howling)
  q      quit

Turn OFF "Direct Monitor" on the Focusrite or you'll hear your dry signal too.

Real amp captures (optional):
  irs/<Preset>.wav   speaker cab IR for that preset, e.g. irs/SRV.wav (irs/default.wav = all presets)
  python rig.py --setup-nam 1   opens the Neural Amp Modeler plugin for preset 1: load a .nam
                                capture in it, close the window, and preset 1 uses that amp from then on
"""
import argparse
import os
import msvcrt
import sys
import time
from pathlib import Path

os.environ.setdefault("SD_ENABLE_ASIO", "1")  # must be set before sounddevice loads PortAudio

import numpy as np
import sounddevice as sd
from pedalboard import (Chorus, Compressor, Convolution, Delay, Distortion, Gain, HighpassFilter,
                        HighShelfFilter, LadderFilter, Limiter, LowpassFilter, LowShelfFilter, Mix,
                        NoiseGate, Pedalboard, PeakFilter, Phaser, Reverb, load_plugin)

HERE = Path(__file__).parent
IR_DIR = HERE / "irs"
NAM_DIR = HERE / "nam"
NAM_PLUGIN = Path(r"C:\Program Files\Common Files\VST3\NeuralAmpModeler.vst3")

SR = 48000  # replaced by the interface's native rate at startup
BLOCK = 128


def cab(cutoff=5000):
    """Speaker cab: thump around 110 Hz, scooped boxiness, presence, and no fizz above the speaker's range."""
    return [
        HighpassFilter(cutoff_frequency_hz=75),
        PeakFilter(cutoff_frequency_hz=110, gain_db=5, q=1.4),
        PeakFilter(cutoff_frequency_hz=400, gain_db=-3, q=1.0),
        PeakFilter(cutoff_frequency_hz=2500, gain_db=3, q=1.2),
        LadderFilter(mode=LadderFilter.Mode.LPF24, cutoff_hz=cutoff, resonance=0.15, drive=1.0),
    ]


def power_amp(presence_db=2):
    """Pushed output tubes: a little extra squish and low-end bloom. This is most of the 'oomph'."""
    return [
        LowShelfFilter(cutoff_frequency_hz=160, gain_db=3),
        Gain(gain_db=4), Distortion(drive_db=5),
        PeakFilter(cutoff_frequency_hz=3500, gain_db=presence_db, q=0.8),
    ]


# Each preset is pedals -> amp (+ cab) -> effects, so a NAM capture can replace just the amp
# and an IR can replace just the cab.

def srv():
    pedals = [
        NoiseGate(threshold_db=-62, ratio=3, release_ms=150),
        # Tube Screamer: mid hump into soft clipping, blended with clean for that bloom
        Mix([
            Pedalboard([HighpassFilter(cutoff_frequency_hz=720), PeakFilter(cutoff_frequency_hz=750, gain_db=6, q=0.7),
                        Gain(gain_db=10), Distortion(drive_db=16), LowpassFilter(cutoff_frequency_hz=3500), Gain(gain_db=-14)]),
            Gain(gain_db=-4),
        ]),
    ]
    # Big Fender (Super Reverb / Vibroverb) on the edge of breakup; 4x10s with lots of low end
    amp = [
        PeakFilter(cutoff_frequency_hz=120, gain_db=6, q=0.8),
        Gain(gain_db=8), Distortion(drive_db=8),
        PeakFilter(cutoff_frequency_hz=500, gain_db=-2, q=0.8),
        HighShelfFilter(cutoff_frequency_hz=3000, gain_db=2),
        *power_amp(),
    ]
    fx = [Reverb(room_size=0.45, damping=0.55, wet_level=0.18, dry_level=0.85, width=0.0)]
    return pedals, amp, 5500, fx


def hendrix():
    pedals = [
        # Fuzz cleans up and sputters as notes die: a gentle gate so it doesn't chop the tail
        NoiseGate(threshold_db=-62, ratio=2, release_ms=250),
        # Fuzz Face: thick and woolly, not buzzy
        Gain(gain_db=10), Distortion(drive_db=20), LowpassFilter(cutoff_frequency_hz=5000), Gain(gain_db=-12),
        # Uni-Vibe: slow throb, kept subtle so it's not seasick
        Phaser(rate_hz=1.0, depth=0.5, centre_frequency_hz=1000, feedback=0.1, mix=0.35),
    ]
    # Marshall Plexi
    amp = [
        PeakFilter(cutoff_frequency_hz=120, gain_db=3, q=0.8),
        PeakFilter(cutoff_frequency_hz=800, gain_db=3, q=0.8),
        Gain(gain_db=6), Distortion(drive_db=8),
        HighShelfFilter(cutoff_frequency_hz=3000, gain_db=2),
        *power_amp(presence_db=3),
    ]
    fx = [
        Delay(delay_seconds=0.3, feedback=0.15, mix=0.08),
        Reverb(room_size=0.35, damping=0.5, wet_level=0.12, dry_level=0.9, width=0.0),
    ]
    return pedals, amp, 5000, fx


def clapton():
    pedals = [
        NoiseGate(threshold_db=-60, ratio=3, release_ms=150),
        # Neck pickup with the tone knob on 0
        LowpassFilter(cutoff_frequency_hz=900), LowpassFilter(cutoff_frequency_hz=1200),
        PeakFilter(cutoff_frequency_hz=650, gain_db=5, q=0.9),
    ]
    # Cranked Marshall
    amp = [
        Gain(gain_db=18), Distortion(drive_db=22),
        HighpassFilter(cutoff_frequency_hz=90),
        PeakFilter(cutoff_frequency_hz=700, gain_db=3, q=0.7),
        *power_amp(presence_db=1),
    ]
    fx = [Reverb(room_size=0.3, damping=0.6, wet_level=0.1, dry_level=0.9, width=0.0)]
    return pedals, amp, 4200, fx


def slowhand():
    pedals = [
        NoiseGate(threshold_db=-62, ratio=3, release_ms=150),
        Compressor(threshold_db=-26, ratio=3, attack_ms=15, release_ms=150),
        # Strat active mid-boost
        PeakFilter(cutoff_frequency_hz=800, gain_db=9, q=0.6),
        HighpassFilter(cutoff_frequency_hz=100),
    ]
    amp = [Gain(gain_db=6), Distortion(drive_db=9), *power_amp()]
    fx = [
        Chorus(rate_hz=0.8, depth=0.2, centre_delay_ms=7, feedback=0.0, mix=0.35),
        Delay(delay_seconds=0.38, feedback=0.25, mix=0.15),
        Reverb(room_size=0.5, damping=0.5, wet_level=0.18, dry_level=0.85, width=0.0),
    ]
    return pedals, amp, 5500, fx


def clean():
    pedals = [
        NoiseGate(threshold_db=-65, ratio=3, release_ms=150),
        Compressor(threshold_db=-22, ratio=2, attack_ms=15, release_ms=120),
    ]
    amp = [
        PeakFilter(cutoff_frequency_hz=120, gain_db=2, q=0.8),
        PeakFilter(cutoff_frequency_hz=500, gain_db=-2, q=0.8),
        HighShelfFilter(cutoff_frequency_hz=3000, gain_db=3),
        Gain(gain_db=6), Distortion(drive_db=1),
        LowShelfFilter(cutoff_frequency_hz=160, gain_db=2),
    ]
    fx = [Reverb(room_size=0.45, damping=0.5, wet_level=0.2, dry_level=0.85, width=0.0)]
    return pedals, amp, 6500, fx


# key -> (name, builder, output level trim in dB so presets are roughly equally loud)
PRESETS = {
    "1": ("SRV", srv, -16.5),
    "2": ("Hendrix", hendrix, -15.0),
    "3": ("Clapton", clapton, -17.0),
    "4": ("Slowhand", slowhand, -10.5),
    "0": ("Clean", clean, 0.0),
}


def load_nam(key):
    """The Neural Amp Modeler plugin with the capture saved by --setup-nam, or None."""
    state = NAM_DIR / f"{key}.state"
    if not (NAM_PLUGIN.exists() and state.exists()):
        return None
    plugin = load_plugin(str(NAM_PLUGIN))
    plugin.raw_state = state.read_bytes()
    return plugin


def build(key):
    """Assemble a preset, swapping in a NAM amp capture and/or cab IR when they exist."""
    name, builder, _ = PRESETS[key]
    pedals, amp, cab_cutoff, fx = builder()
    sources = []

    nam = load_nam(key)
    if nam is not None:
        amp = [nam]
        sources.append("NAM amp")

    ir = next((p for p in (IR_DIR / f"{name}.wav", IR_DIR / "default.wav") if p.exists()), None)
    if ir is not None:
        speaker = [Convolution(str(ir), mix=1.0)]
        sources.append(f"IR {ir.name}")
    elif nam is not None:
        speaker = []  # most NAM captures are amp-only, but some include the cab; drop an IR in irs/ if it's fizzy
    else:
        speaker = cab(cab_cutoff)

    return Pedalboard(pedals + amp + speaker + fx), sources


NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def detect_pitch(x, sr, fmin=60.0, fmax=1000.0, threshold=0.15):
    """YIN pitch detection. Returns frequency in Hz, or None if there's no clear note."""
    x = x - x.mean()
    if np.sqrt(np.mean(x ** 2)) < 1e-3:
        return None
    tau_min, tau_max = int(sr / fmax), int(sr / fmin)
    w = len(x) - tau_max
    if w < tau_max:
        return None
    # difference function d(tau) = sum (x[j] - x[j+tau])^2 via FFT cross-correlation
    n = 1 << int(np.ceil(np.log2(len(x) + w)))
    corr = np.fft.irfft(np.fft.rfft(x, n) * np.conj(np.fft.rfft(x[:w], n)), n)[:tau_max + 1]
    energy = np.concatenate(([0.0], np.cumsum(x ** 2)))
    e0 = energy[w]
    e_tau = energy[np.arange(tau_max + 1) + w] - energy[np.arange(tau_max + 1)]
    d = e0 + e_tau - 2 * corr
    d[0] = 0
    cmndf = np.ones_like(d)
    cmndf[1:] = d[1:] * np.arange(1, len(d)) / np.maximum(np.cumsum(d[1:]), 1e-12)

    below = np.where(cmndf[tau_min:] < threshold)[0]
    if len(below) == 0:
        return None
    tau = below[0] + tau_min
    while tau + 1 < len(cmndf) and cmndf[tau + 1] < cmndf[tau]:
        tau += 1
    if 0 < tau < len(cmndf) - 1:  # parabolic interpolation for sub-sample accuracy
        a, b, c = cmndf[tau - 1], cmndf[tau], cmndf[tau + 1]
        tau = tau + 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) else tau
    return sr / tau


# low (6th) string to high (1st)
TUNINGS = [
    ("Standard", "E2 A2 D3 G3 B3 E4"),
    ("Eb / half-step down (SRV, Hendrix)", "Eb2 Ab2 Db3 Gb3 Bb3 Eb4"),
    ("Drop D", "D2 A2 D3 G3 B3 E4"),
    ("Open G (Keith Richards)", "D2 G2 D3 G3 B3 D4"),
    ("Open E (slide, Duane Allman)", "E2 B2 E3 G#3 B3 E4"),
    ("Open D (slide blues)", "D2 A2 D3 F#3 A3 D4"),
    ("DADGAD (Page, 'Kashmir')", "D2 A2 D3 G3 A3 D4"),
    ("D Standard / whole-step down", "D2 G2 C3 F3 A3 D4"),
    ("Chromatic", None),
]


def note_to_midi(name):
    flats = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}
    pitch, octave = name[:-1], int(name[-1])
    return NOTE_NAMES.index(flats.get(pitch, pitch)) + 12 * (octave + 1)


def tuner_display(freq, tuning=TUNINGS[0]):
    tuning_name, strings = tuning
    if freq is None:
        return f"TUNER [{tuning_name}]  play a single string...  (n = next tuning)"
    midi = 69 + 12 * np.log2(freq / 440.0)
    if strings is None:
        target = int(round(midi))
        label = f"{NOTE_NAMES[target % 12]}{target // 12 - 1}"
    else:
        names = strings.split()
        targets = [note_to_midi(n) for n in names]
        i = int(np.argmin([abs(midi - t) for t in targets]))
        target = targets[i]
        label = f"string {6 - i}: {names[i]}"
    cents = (midi - target) * 100
    pos = int(np.clip(round(cents / 5), -10, 10))  # 5 cents per character
    bar = ["-"] * 21
    bar[10] = "|"
    bar[10 + pos] = "O" if abs(cents) < 3 else "o"
    verdict = "IN TUNE" if abs(cents) < 3 else ("tune UP" if cents < 0 else "tune DOWN")
    return (f"TUNER [{tuning_name}]  {label:<13} {cents:+6.1f}c  [{''.join(bar)}]  {verdict:<9} "
            f"{freq:6.1f} Hz")


# Non-western scales as cents above the root (50s = quarter tones, played by bending the fret below).
# (name, cents, usual root, flavour)
SCALES = [
    ("Maqam Rast", "0 200 350 500 700 900 1050", "C", "Arabic 'mother' maqam: neutral 3rd and 7th, proud and bright"),
    ("Maqam Bayati", "0 150 300 500 700 800 1000", "D", "Arabic: the most common maqam in folk song; warm, earthy"),
    ("Maqam Hijaz", "0 100 400 500 700 800 1000", "D", "Arabic/Turkish/klezmer (Freygish): that classic 'desert' sound"),
    ("Maqam Saba", "0 150 300 400 700 800 1000", "D", "Arabic: sorrowful, the flat 4th gives it a crying quality"),
    ("Maqam Sikah", "50 200 400 600 750 900 1100", "Eb", "Arabic: tonic is E~ (Eb bent a quarter up); spiritual, hovering"),
    ("Maqam Nahawand", "0 200 300 500 700 800 1100", "C", "Arabic: like harmonic minor, romantic"),
    ("Raga Yaman", "0 200 400 600 700 900 1100", "C", "North Indian evening raga: sharp 4th, serene and devotional"),
    ("Raga Bhairav", "0 100 400 500 700 800 1100", "C", "North Indian dawn raga: flat 2nd and 6th, solemn and grand"),
    ("Raga Todi", "0 100 300 600 700 800 1100", "C", "North Indian morning raga: tense, yearning"),
    ("Raga Kafi", "0 200 300 500 700 900 1000", "D", "North Indian: Dorian-like, folk and spring songs"),
    ("Raga Bhupali", "0 200 400 700 900", "C", "North Indian pentatonic: open, peaceful"),
    ("Hirajoshi", "0 200 300 700 800", "A", "Japanese koto scale: dark and spacious"),
    ("In (Miyako-bushi)", "0 100 500 700 800", "E", "Japanese: shamisen and shakuhachi, haunting"),
    ("Pelog (approx.)", "0 120 270 540 670 800 950", "E", "Javanese gamelan: not 12-tone at all; bend to taste"),
    ("Slendro (approx.)", "0 240 480 720 960", "D", "Javanese gamelan: 5 nearly equal steps, floaty"),
    ("Hungarian minor", "0 200 300 600 700 800 1100", "A", "Gypsy/Romani: two augmented 2nds, fiery"),
]
FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def cents_name(cents):
    """Note name for a pitch in cents above C; quarter tones are written as half-flats, e.g. E~ = E half-flat."""
    semis = cents / 100
    if abs(semis - round(semis)) < 0.26:
        return FLAT_NAMES[int(round(semis)) % 12]
    return FLAT_NAMES[int(np.ceil(semis)) % 12] + "~"


def scale_degrees(scale, root):
    return [int(c) for c in scale[1].split()], FLAT_NAMES.index(root)


def fretboard(scale, root, tuning, frets=12):
    """ASCII fretboard of the scale for the current tuning. A '~' note = bend that fret up a quarter step."""
    degrees, root_pc = scale_degrees(scale, root)
    strings = (tuning[1] or TUNINGS[0][1]).split()
    lines = [f"{scale[0]} on {root}: " + " ".join(cents_name(root_pc * 100 + d) for d in degrees),
             f"  {scale[3]}",
             f"  tuning: {tuning[0] if tuning[1] else 'Standard'}   [R] = root   X~ = half-flat: bend that fret a quarter step up",
             "      " + "".join(f"{f:<5}" for f in range(frets + 1))]
    for name in reversed(strings):
        open_midi = note_to_midi(name)
        cells = []
        for f in range(frets + 1):
            rel = ((open_midi + f - root_pc) * 100) % 1200
            if rel == degrees[0]:
                cells.append("[R] ")
            elif (rel + 50) % 1200 == degrees[0]:
                cells.append("[R~]")
            elif rel in degrees:
                cells.append(f"{cents_name((open_midi + f) * 100):<4}")
            elif (rel + 50) % 1200 in degrees:
                cells.append(f"{cents_name((open_midi + f) * 100 + 50):<4}")
            else:
                cells.append(" .  ")
        lines.append(f"{name:>4} |" + "|".join(cells) + "|")
    return "\n".join(lines)


def scale_display(freq, scale, root):
    degrees, root_pc = scale_degrees(scale, root)
    if freq is None:
        return f"SCALE {scale[0]} on {root}: play single notes...  (s = next scale, r = root)"
    midi = 69 + 12 * np.log2(freq / 440.0)
    rel = (midi * 100 - root_pc * 100) % 1200
    dists = [((rel - d + 600) % 1200) - 600 for d in degrees]  # signed, wrapped to -600..600
    i = int(np.argmin(np.abs(dists)))
    off = dists[i]
    note = cents_name(root_pc * 100 + degrees[i])
    pos = int(np.clip(round(off / 5), -10, 10))
    bar = ["-"] * 21
    bar[10] = "|"
    bar[10 + pos] = "O" if abs(off) < 10 else "o"
    if degrees[i] % 100 == 50 and -60 <= off <= -10:
        verdict = "bend more (quarter step)"
    elif abs(off) > 35:
        verdict = "outside the scale"
    else:
        verdict = "IN SCALE" if abs(off) < 10 else ("bend more" if off < 0 else "too sharp")
    return f"SCALE {scale[0]} on {root}  degree {i + 1} ({note:<3}) {off:+5.0f}c [{''.join(bar)}] {verdict}"


class Rig:
    def __init__(self, input_channel=0):
        self.boards = {}
        for k in PRESETS:
            self.boards[k], sources = build(k)
            if sources:
                print(f"  {PRESETS[k][0]}: using {', '.join(sources)}")
        self.current = "0"  # start clean and quiet; pick a tone once you know it's not howling
        self.previous = None
        self.fade_pos = 10 ** 9
        self.input_channel = input_channel
        self.input_trim_db = 0.0
        self.master_db = -12.0
        self.muted = False
        self.tuner = False
        self.listen = False  # feed the pitch detector without muting (scale trainer)
        self.tuner_buf = np.zeros(8192, np.float32)  # raw input for the tuner, newest at the end
        # kill sub-bass rumble before it gets distorted into mush
        self.input_hpf = Pedalboard([HighpassFilter(cutoff_frequency_hz=70), HighpassFilter(cutoff_frequency_hz=70)])
        self.limiter = Pedalboard([Limiter(threshold_db=-1.0, release_ms=50)])  # protects your ears
        self.in_peak = 0.0
        self.out_peak = 0.0
        self.xruns = 0

    def set_gate_floor(self, noise_db):
        """Make every noise gate close above the measured hiss/hum, so silence stays silent."""
        floor = noise_db + 8
        for board in self.boards.values():
            for plugin in board:
                if isinstance(plugin, NoiseGate):
                    plugin.threshold_db = max(plugin.threshold_db, floor)
        return floor

    def switch(self, key):
        if key == self.current:
            return
        self.boards[key].reset()
        self.previous, self.current, self.fade_pos = self.current, key, 0

    def run_board(self, key, x):
        y = self.boards[key](x, SR, reset=False)
        return y * 10 ** (PRESETS[key][2] / 20)

    def callback(self, indata, outdata, frames, time_info, status):
        if status:
            self.xruns += 1
        raw = indata[:, self.input_channel].astype(np.float32)
        if self.tuner or self.listen:
            self.tuner_buf = np.concatenate((self.tuner_buf[frames:], raw))
        x = raw * 10 ** (self.input_trim_db / 20)
        x = self.input_hpf(x[np.newaxis, :], SR, reset=False)
        self.in_peak = max(self.in_peak * 0.9, float(np.abs(x).max()))

        y = self.run_board(self.current, x)
        fade_len = int(0.03 * SR)  # 30 ms crossfade when switching presets
        if self.fade_pos < fade_len and self.previous:
            old = self.run_board(self.previous, x)
            ramp = np.clip((self.fade_pos + np.arange(frames)) / fade_len, 0, 1).astype(np.float32)
            y = old * (1 - ramp) + y * ramp
            self.fade_pos += frames

        y = self.limiter(y * 10 ** (self.master_db / 20), SR, reset=False)[0]
        self.out_peak = max(self.out_peak * 0.9, float(np.abs(y).max()))

        outdata[:] = 0 if (self.muted or self.tuner) else y[:, np.newaxis]


def find_device(name_part, kind, hostapi_name):
    hostapis = sd.query_hostapis()
    for i, d in enumerate(sd.query_devices()):
        if hostapis[d["hostapi"]]["name"] != hostapi_name:
            continue
        if name_part.lower() in d["name"].lower() and d[f"max_{kind}_channels"] > 0:
            return i
    return None


def pick_devices(name):
    """Best driver first: ASIO (one shared clock, so latency can't creep), then kernel streaming, then WASAPI."""
    asio = find_device(name, "input", "ASIO")
    if asio is not None:
        return asio, asio, "ASIO", 0  # blocksize 0 = follow the buffer size set in the Focusrite control panel
    ks_in, ks_out = find_device("wc4800", "input", "Windows WDM-KS"), find_device("wr4800", "output", "Windows WDM-KS")
    if ks_in is not None and ks_out is not None:
        return ks_in, ks_out, "WDM-KS", BLOCK
    return find_device(name, "input", "Windows WASAPI"), find_device(name, "output", "Windows WASAPI"), "WASAPI", BLOCK


def meter(level, width=20):
    db = 20 * np.log10(max(level, 1e-6))
    filled = int(np.clip((db + 60) / 60, 0, 1) * width)
    return "#" * filled + "-" * (width - filled) + ("!" if level >= 0.99 else " ")


def setup_nam(key):
    if not NAM_PLUGIN.exists():
        sys.exit(f"Neural Amp Modeler isn't installed (expected {NAM_PLUGIN}).\n"
                 "Get it free from https://www.neuralampmodeler.com/ and run this again.")
    NAM_DIR.mkdir(exist_ok=True)
    state = NAM_DIR / f"{key}.state"
    plugin = load_plugin(str(NAM_PLUGIN))
    if state.exists():
        plugin.raw_state = state.read_bytes()
    print(f"Load a .nam capture for {PRESETS[key][0]} in the plugin window (leave its IR slot empty "
          "unless you want it), then close the window.")
    plugin.show_editor()
    state.write_bytes(plugin.raw_state)
    print(f"Saved. {PRESETS[key][0]} will use this amp next time you start the rig. "
          f"Delete {state} to go back to the built-in amp.")


def main():
    global SR
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="Focusrite", help="part of the audio interface name")
    ap.add_argument("--input-channel", type=int, choices=[1, 2], help="skip auto-detect and use this input")
    ap.add_argument("--setup-nam", choices=list(PRESETS), metavar="PRESET_KEY",
                    help="load a Neural Amp Modeler capture into a preset (1-4 or 0)")
    args = ap.parse_args()

    if args.setup_nam:
        return setup_nam(args.setup_nam)

    in_dev, out_dev, driver, blocksize = pick_devices(args.device)
    if in_dev is None or out_dev is None:
        sys.exit(f"Couldn't find an audio device matching '{args.device}'. Devices:\n{sd.query_devices()}")
    SR = int(sd.query_devices(in_dev)["default_samplerate"])  # run at the interface's own rate, no resampling

    def record(seconds):
        x = sd.rec(int(seconds * SR), samplerate=SR, channels=2, device=in_dev, dtype="float32")
        sd.wait()
        hpf = Pedalboard([HighpassFilter(cutoff_frequency_hz=70), HighpassFilter(cutoff_frequency_hz=70)])
        x = hpf(x.T.copy(), SR)[:, SR // 4:]  # skip the filter settling
        return 20 * np.log10(np.abs(x).max(axis=1) + 1e-9)  # peak dB per input

    print("Measuring noise floor - keep your hands OFF the strings for 2 seconds...")
    noise_db = record(2)
    if args.input_channel:
        channel = args.input_channel - 1
    else:
        input("Now press Enter and strum the guitar hard for 3 seconds (stay quiet otherwise)...")
        strum_db = record(3)
        rise = strum_db - noise_db
        channel = int(np.argmax(rise))
        print(f"  input 1 jumped {rise[0]:+.0f} dB, input 2 jumped {rise[1]:+.0f} dB -> guitar is on input {channel + 1}")
        if rise[channel] < 15:
            sys.exit("Didn't hear the guitar clearly. Check the cable / INST button / gain knob, "
                     "or force it with: python rig.py --input-channel 2")

    rig = Rig(input_channel=channel)
    gate_db = rig.set_gate_floor(noise_db[channel])
    print(f"Noise floor {noise_db[channel]:.0f} dBFS -> gates set to at least {gate_db:.0f} dBFS")
    print("The mic on the other input is ignored. Headphones are still the safest bet with the mic plugged in.")

    stream = sd.Stream(samplerate=SR, blocksize=blocksize, device=(in_dev, out_dev), channels=(2, 2),
                       dtype="float32", latency="low", callback=rig.callback)

    print(__doc__)
    with stream:
        print(f"Driver: {driver} @ {SR} Hz, latency {(stream.latency[0] + stream.latency[1]) * 1000:.1f} ms round trip"
              + ("  (lower the buffer size in Focusrite Control to cut this)" if driver == "ASIO" else "") + "\n")
        readings = []
        tuning = 0
        scale = None  # index into SCALES while the scale trainer is on
        root = None

        def show_scale():
            sys.stdout.write("\r" + " " * 110 + "\r")
            print(fretboard(SCALES[scale], root, TUNINGS[tuning]) + "\n")

        while True:
            while msvcrt.kbhit():
                k = msvcrt.getwch().lower()
                if k == "q":
                    print()
                    return
                if k in PRESETS:
                    rig.switch(k)
                elif k == "t":
                    rig.tuner = not rig.tuner
                    readings.clear()
                elif k == "n":
                    tuning = (tuning + 1) % len(TUNINGS)
                    if scale is None:
                        rig.tuner = True
                    else:
                        show_scale()
                elif k == "s":
                    scale = 0 if scale is None else scale + 1
                    if scale >= len(SCALES):
                        scale = None
                        print("\nScale trainer off.")
                    else:
                        root = SCALES[scale][2]
                        rig.tuner = False
                        show_scale()
                    rig.listen = scale is not None
                    readings.clear()
                elif k == "r" and scale is not None:
                    root = FLAT_NAMES[(FLAT_NAMES.index(root) + 1) % 12]
                    show_scale()
                elif k == "[":
                    rig.input_trim_db = max(rig.input_trim_db - 3, -24)
                elif k == "]":
                    rig.input_trim_db = min(rig.input_trim_db + 3, 24)
                elif k == "-":
                    rig.master_db = max(rig.master_db - 3, -60)
                elif k in "+=":
                    rig.master_db = min(rig.master_db + 3, 6)
                elif k == "m":
                    rig.muted = not rig.muted
                elif k == "i":
                    rig.input_channel = 1 - rig.input_channel
            if rig.tuner or rig.listen:
                freq = detect_pitch(rig.tuner_buf.astype(np.float64), SR)
                readings = (readings + [freq])[-5:] if freq else []
                heard = float(np.median(readings)) if readings else None
            if rig.tuner:
                status = "\r" + tuner_display(heard, TUNINGS[tuning])
            elif scale is not None:
                status = f"\r[{PRESETS[rig.current][0]}] " + scale_display(heard, SCALES[scale], root)
            else:
                flag = "MUTED" if rig.muted else ""
                status = (f"\r[{PRESETS[rig.current][0]:<8}] in{rig.input_channel + 1} {meter(rig.in_peak)} "
                          f"out {meter(rig.out_peak)} trim {rig.input_trim_db:+.0f}dB vol {rig.master_db:+.0f}dB "
                          f"glitches {rig.xruns} {flag:<6}")
            sys.stdout.write(status.ljust(110))
            sys.stdout.flush()
            time.sleep(0.05)


if __name__ == "__main__":
    main()
