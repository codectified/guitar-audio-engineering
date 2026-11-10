# guitar-audio-engineering

A **live guitar amp-sim / practice rig in Python** (`rig/`): plug a guitar into a USB audio interface and
play through presets modeled on SRV, Hendrix, Clapton, BB King, Howlin' Wolf, Muddy Waters, Albert King,
Freddie King and Derek Trucks. Also has a tuner with alternate tunings, an auto-wah, and a maqam/raga
scale trainer.

## Quick start (Windows)

You need:

- **Windows** and a **USB audio interface with 2 inputs** (built and tested on a Focusrite Scarlett Solo).
  Turn the interface's **Direct Monitor off**, and use headphones if a mic is plugged in.
- **Python 3.11+** from [python.org](https://www.python.org/downloads/). Tick "Add python.exe to PATH" when you install it.
- Optional but **strongly recommended**: the free **TONE3000** plugin from
  [neuralampmodeler.com/users](https://neuralampmodeler.com/users). Presets 1–9 and `d` use real amp
  captures (Neural Amp Modeler) through it. Without it the rig still works, using its built-in amp sims.
  Use the default install location (`C:\Program Files\Common Files\VST3\TONE3000.vst3`).

Then:

```
git clone https://github.com/codectified/guitar-audio-engineering.git
cd guitar-audio-engineering
pip install -r requirements.txt
```

Double-click **`rig/Guitar Rig.bat`** (or run `python rig/rig.py`). When it starts it measures the noise,
asks you to strum, and picks the guitar input for you. Press `h` for the menu. Keys only work while the
rig's window is focused.

| Key | What it does |
| --- | --- |
| `1`–`9`, `d`, `o`, `0` | presets (`o` = octave fuzz, `0` = clean) |
| `[` / `]` | input trim (more = more drive) |
| `-` / `+` | master volume |
| `m` | mute (hit this if it ever howls) |
| `w` / `e` | auto-wah on/off / sensitivity |
| `t` | tuner on/off. **The tuner mutes the output**: no sound? press `t` |
| `n` | next tuning (turns the tuner on) |
| `s` / `r` | scale trainer: next scale / next root |
| `x` / `q` | restart / quit |

## Quick start (Mac)

Clone the repo as above, then double-click **`rig/Guitar Rig.command`** (or run it from Terminal). The first
run sets up a Python environment in `.venv/` (needs Python 3.11+, e.g. `brew install python`). The first time,
macOS asks to let Terminal use the microphone: say yes, or the rig hears silence.

- **Scarlett Solo:** picked automatically, about 8 ms round trip.
- **Positive Grid Spark GO:** also works (guitar in and sound out over its USB cable), but about 35 ms round trip,
  so the Scarlett is better for real playing. Put the Spark on a clean preset so you don't hear its amp on top.
- The rig runs at the interface's own sample rate on a Mac. If a Scarlett is set to 192 kHz in
  Audio MIDI Setup, that works but uses 4x the CPU; 48 kHz is plenty.
- NAM amp captures need the free **Gateway** plugin (the Mac name for the TONE3000 plugin): the macOS installer
  on [neuralampmodeler.com/users](https://neuralampmodeler.com/users) puts it at `/Library/Audio/Plug-Ins/VST3/Gateway.vst3`.
  Not tested on a Mac yet; without it, the presets use their built-in amp sims.

### If your interface isn't a Focusrite

`python rig/rig.py --device "part of your interface's name"`. Run
`python -c "import sounddevice; print(sounddevice.query_devices())"` to see the names. Install your
interface's **ASIO driver** if it has one: it gives the lowest latency. Without one the rig falls back to WASAPI.
If you already know which input the guitar is on, `--input-channel 2` (or `1`) skips the strum check.

### Latency

The rig prints the round-trip latency at startup. If it feels laggy, lower the buffer size in your
interface's control panel (Focusrite Control → Settings: 64–96 samples, Safe Mode off) and press `x`.

## Amp captures (credits)

The NAM captures in `rig/nam/captures/` were made by TONE3000 community members and are included
here so the presets work out of the box:

- **1964 Fender Super Reverb** (20 settings) by **maestrodimusica**
- **Marshall 1959 Plexi Super Lead** (Driven, + Boost, Low Gain) by **phrygian68**

Find more at [tone3000.com](https://www.tone3000.com). `rig/nam/<preset>.state` is the plugin's saved
state for each preset, with the capture embedded. To swap one: `python rig/rig.py --setup-nam 1` opens the
plugin. Drag a `.nam` file onto it, then close the window.

## Status

**Active**, created 2026-10-02. Runs on real hardware. See `HANDOFF.md` for what's verified, what isn't,
and next steps. Other directions (recording, mixing, gear) are still open.

## Master Hub summary

See `C:\dev\hq\projects\guitar-audio-engineering\overview.md` for the HQ-level pointer. This file is the
full detail; that one is a summary. If they ever conflict, this file wins.
