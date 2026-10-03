# Handoff — 2026-10-02

## Where things stand

`rig/rig.py` is a live guitar amp-sim in Python (pedalboard + sounddevice).
Launch with `rig/Guitar Rig.bat` (or `python rig/rig.py`).

Signal path: Squier Strat → Focusrite (ASIO, 44.1 kHz) → presets → Focusrite outs.

- Presets: `1` SRV, `2` Hendrix, `3` Clapton (Cream "woman tone"), `4` Slowhand (80s Clapton), `0` Clean.
  Each preset = pedals → amp → cab → effects, levels matched to ~-15 dBFS RMS.
- Tuner (`t`) with alternate tunings (`n`): Standard, Eb, Drop D, Open G, Open E, Open D, DADGAD, D Standard, Chromatic.
- Scale trainer (`s` scale, `r` root): 16 maqams/ragas/Japanese/gamelan scales; prints an ASCII
  fretboard for the current tuning, quarter tones shown as `X~` (bend the fret a quarter step up),
  live readout of which degree you're on and whether the bend landed.
- Startup: measures noise floor, asks you to strum, auto-picks the guitar input, sets gates above the noise.

## Hardware facts (learned the hard way)

- **Input 1 = microphone, input 2 = guitar.** Reading the mic caused a howling feedback loop.
  Auto-detect handles it; `--input-channel 2` forces it.
- Use the **Focusrite USB ASIO** driver (`SD_ENABLE_ASIO=1`, set in rig.py). WASAPI/WDM-KS
  latency crept up over time (separate in/out clocks). ASIO round trip ~22 ms at default buffer;
  lower it in Focusrite Control → Settings (buffer 64–96, Safe Mode off).
- Direct Monitor on the Focusrite must be OFF.

## Verified vs. not

- Verified offline: all presets run (<2% CPU budget), level matching, tuner accuracy
  (0.0 cents on exact tones), tunings, scale maps and bend detection, full `main()` with fake audio/keys.
- **Not yet verified by ear on the real guitar:** the reworked Hendrix preset and the added
  "oomph" (cab low-end bump + power-amp stage). Ask Omar how they sound.
- **Untested:** Neural Amp Modeler integration (`--setup-nam N`, `nam/<key>.state`) and
  cab IR loading from the real plugin (IR loading itself was tested with a synthetic IR).

## Next steps

1. Omar installs NAM: `rig/plugins/NeuralAmpModeler Installer.exe` (needs admin — Claude was not
   permitted to run it). Then test `python rig/rig.py --setup-nam 1` end to end.
2. Get captures from TONE3000 (free account required; API needs OAuth, no anonymous download):
   Fender Super Reverb for SRV, Marshall Plexi for Hendrix/Clapton.
3. Optional cab IRs → `rig/irs/<Preset>.wav` or `rig/irs/default.wav`.
4. Tune presets by ear based on Omar's feedback.

## Gotchas

- The old copy at `C:\Users\andre\guitar-rig` is the pre-move original; this repo is now canonical.
- An automatic feedback-detector was tried and removed: it couldn't tell a howl from sustained fuzz.
- Long bash heredocs with mixed `'''` quoting got mangled once; prefer the Edit tool for multi-line patches.
