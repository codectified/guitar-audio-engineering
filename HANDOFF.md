# Handoff — 2026-10-03

## Where things stand

`rig/rig.py` is a live guitar amp-sim in Python (pedalboard + sounddevice).
Launch with `rig/Guitar Rig.bat` (or `python rig/rig.py`).

Signal path: Squier Strat → Focusrite (ASIO, 48 kHz) → presets → Focusrite outs.

- Presets: `1` SRV, `2` Hendrix, `3` Clapton (Cream "woman tone"), `4` Slowhand (80s Clapton),
  `5` BB King, `6` Howlin' Wolf (Hubert Sumlin), `7` Muddy Waters, `8` Albert King, `9` Freddie King,
  `d` Derek Trucks (SG + slide, pushed Super Reverb, tape echo; suggests Open E), `0` Clean.
  The menu (`h`) shows each preset's pedals / amp (capture name) / cab / fx.
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
- **Run at 48 kHz** (rig.py does, falling back to the device default). Windows shared mode uses the
  Focusrite at 48 kHz; opening ASIO at 44.1 kHz switched the hardware clock under Windows and garbled
  system audio until a reboot. Quick fix if it happens again: unplug/replug the Focusrite USB.

## Verified vs. not

- Verified offline: all presets run (<2% CPU budget), level matching, tuner accuracy
  (0.0 cents on exact tones), tunings, scale maps and bend detection, full `main()` with fake audio/keys.
- **Not yet verified by ear on the real guitar:** the reworked Hendrix preset and the added
  "oomph" (cab low-end bump + power-amp stage). Ask Omar how they sound.
- **NAM amps (2026-10-03):** presets 1–4 now use real amp captures via the TONE3000 plugin.
  Verified offline: each preset plays its capture, levels within ~1.5 dB of each other and Clean,
  preset switching OK, <10% CPU at a 64-sample buffer. **Not yet heard on the real guitar.**
- **Untested:** cab IR loading from a real IR file (tested with a synthetic IR only).

## Next steps

0. (2026-10-03) Omar is rebooting to clear garbled system audio, then starts the rig for the first
   time with NAM amps at 48 kHz. Ask how presets 1–4 sound and whether system audio stayed normal.

1. Omar plays the NAM presets and says how they sound. If one is too clean/dirty, there are 20
   Super Reverb settings and 3 Plexi settings in `rig/nam/captures/` to swap in.
2. Optional cab IRs → `rig/irs/<Preset>.wav` or `rig/irs/default.wav` (the built-in cab filter is
   what the amp-only captures run into now). The Super Reverb capture's page says matching speaker IRs are available separately.
3. Tune presets by ear based on Omar's feedback.

## NAM setup (how it works now)

- Plugin: **TONE3000** (`C:\Program Files\Common Files\VST3\TONE3000.vst3`), the NAM author's
  "Gateway" build from neuralampmodeler.com/users. The old NeuralAmpModeler 0.7.13 in `rig/plugins/`
  can't read current TONE3000 captures (A2 / "SlimmableContainer", format 0.7.0). Point pedalboard
  at the binary inside the bundle; it can't scan the folder.
- Captures (free, no account needed) are in `rig/nam/captures/`: SRV = Super Reverb "Vib, V5 T5 M5 B5",
  Hendrix = Plexi Driven, Clapton = Plexi + Boost, Slowhand = Plexi Low Gain.
- `rig/nam/<key>.state` is the plugin's saved state (ignored by git). The plugin embeds the whole
  model in it, so writing a model path in by hand doesn't work. `--setup-nam N` opens the plugin
  window titled "Pedalboard": drag a `.nam` file onto a chain block, then close the window.
  The "TONE3000" standalone app is separate and doesn't affect the rig.
- These states were made by splitting a 4-amp plugin preset (`%APPDATA%\TONE3000\Presets\custom.t3kpreset`)
  into one block each. Format: JUCE base64 VST3 state → `T3KB` + JUCE ValueTree; amps are
  `ChainSnapshot/ChainBlocks/ChainBlock` nodes with `type=nam`, `toneJson` and an embedded `ModelCache`.
- Presets 5–9 (added 2026-10-03) got states built directly from capture files: copy a `type=nam`
  ChainBlock, set `toneJson` (title, model id, file URL), `activeModelId`, and `ModelCache/CachedModel`
  `modelId` + `data` (the raw .nam bytes, JUCE var marker 0x08). Verified by distortion on a sine
  (the plugin's log is unreliable). So any capture can be wired in without the GUI.
- The plugin normalizes its output, so NAM presets use `NAM_TRIM_DB` instead of the built-in trims.
  It reports 29 samples of latency, so its first block after a reset is short (padded in `run_board`).

## Gotchas

- The old copy at `C:\Users\andre\guitar-rig` is the pre-move original; this repo is now canonical.
- An automatic feedback-detector was tried and removed: it couldn't tell a howl from sustained fuzz.
- Long bash heredocs with mixed `'''` quoting got mangled once; prefer the Edit tool for multi-line patches.
