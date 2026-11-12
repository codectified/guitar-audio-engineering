# Handoff — 2026-10-04

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
- Startup: measures noise floor (quietest 50 ms RMS windows, so a stray pluck doesn't skew it), asks you
  to strum, auto-picks the guitar input, sets gates 8 dB above the noise, capped at -58 dBFS.
  `--input-channel 2` skips the strum. Startup recording times out with a "replug the Focusrite"
  message instead of hanging if the interface stops delivering audio.
- `x` restarts in place (exit code 11/12 → `Guitar Rig.bat` relaunches with `--input-channel`).

## 2026-10-07

- Repo is public for Omar's friends. `rig/nam/` (preset states + captures, ~10 MB) is now committed with
  creator credits in README; README has a clone-and-play quick start and `requirements.txt`. The TONE3000
  plugin itself is not committed (third-party binary, no redistribution license); README links it.
  Untested: whether the committed `.state` files load on another machine (they embed the model, so they should).
- Preset switches now overwrite the previous two-line announcement in place (ANSI cursor-up; `enable_ansi()`
  turns on VT processing for the classic console). Verified live in Windows Terminal.
- "Stuck in tuner" report: not a bug. The tuner (`t`, or `n`) mutes output, and keys only reach the rig while its
  window is focused. Pressing `t` turned it off.
- Latency read 89.8 ms after the 2026-10-06 blue screen/reboot (was ~22 ms): Focusrite buffer likely reset.
- 2026-10-06 17:13 the PC blue-screened (0x1A MEMORY_MANAGEMENT); also port exhaustion and Wi-Fi driver
  failures that day. No USB/Focusrite errors. The rig has no log and no dead-stream watchdog; Omar declined both for now.

## Mac port (2026-11-05)

- `rig.py` runs on macOS too: terminal keys via termios (`keypresses()`), `enable_ansi()` is a no-op, Core Audio
  device picking (Scarlett, or the Spark GO's separate 1-in / 2-out devices), status line clipped to the
  terminal width (padding to 110 wrapped and scrolled in narrow windows). Launcher: `rig/Guitar Rig.command`
  (makes `.venv/` on first run, same x-restart loop as the .bat).
- Core Audio runs at the device's own rate: forcing 48 kHz on the Spark GO (44.1 only) resampled, added
  latency and dropped out. Scarlett: `latency=0.003` gives ~8 ms at its native rate (it defaulted to 192 kHz);
  Spark GO: blocksize 64 + "low" gives ~35 ms, stable (smaller dropped out).
- Verified live on the Spark GO via a scripted pseudo-terminal: startup, presets, `h`, `w`, `m`, `q` (exit 0),
  `x` (exit 11). Not verified: by ear on the Mac; whether the Spark's USB input is dry; TONE3000 on macOS and
  whether the Windows-made `.state` files load there.
- **NAM on the Mac (2026-11-05):** the Mac installer of the plugin (neuralampmodeler.com/users, "Gateway" v1.0.1)
  installs `/Library/Audio/Plug-Ins/VST3/Gateway.vst3`. It is the classic NAM plugin format, not the Windows
  TONE3000 chain format: it **rejects the Windows `.state` files** (falls back to a blank state, clean passthrough).
  Its state stores the capture's *path*, so `load_nam()` reads the capture title from the Windows state,
  finds the matching file in `nam/captures/` (`find_capture`) and builds a Gateway state (`gateway_state`).
  Verified offline: all 10 presets load their capture and distort a sine (THD 0.26-0.41). `--setup-nam` on a
  Mac would save a Gateway state that the Windows plugin can't read, so make new presets on the PC.
- Levels with Gateway on a synthetic pluck: -24 dB (Hendrix) to -34 dB (Muddy) vs Clean -33.5; `NAM_TRIM_DB`
  was measured with the Windows plugin and a different test signal. Not retuned; check by ear.

## Octave fuzz preset `o` (2026-11-10)

- Built from a description, no audio clip: Ariel Posen's tone ("octave fuzz feeding most of it, then a plugin
  adding that specific hair and squash"; Dave Navarro asked if it was a ring modulator).
- `Octaver` (rig.py) runs in front of the preset's board via `PRE_STAGES`/`Rig.pre` (pedalboard has no rectifier):
  octave up = full-wave rectified 120 Hz-2.5 kHz band; octave down = Schmitt-trigger flip-flop on the low-passed
  note, as a square shaped by a 30 ms envelope (multiplying the guitar by the flip-flop instead made the
  1.5x-pitch sideband louder than the sub above the low strings). Mix: dry 0.3, up 0.5, down 0.9.
  Omar (2026-11-12): v1 (up only) was "cool but the clip is way nastier... almost like a bass octave".
  The reel (instagram.com/reel/DfkXTVzJGOn) needs an Instagram login to download. Then fuzz, a hard-clipped top-end
  "hair" blend, a 10:1 / 2 ms compressor ("squash"), and a lightly driven built-in Marshall-ish amp.
- Verified offline: up 330 -> 660 Hz; down 82 -> 41 Hz ... 660 -> 330 Hz (sub strongest everywhere); level
  -26 dB on the synthetic pluck (mid-pack), ~3% CPU.
  **Not heard yet.** If Omar sends a clip, match the EQ / octave amount / compression to it.

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
- **2026-10-04 ~4:20 am: the ASMedia USB 3.1 host controller crashed** (Device Manager: Error), taking
  the Focusrite with it after ~8 h of streaming; replugging into the same port did nothing. Reset:
  admin `pnputil /restart-device "PCI\VEN_1B21&DEV_1242&SUBSYS_09611028&REV_00\4&1EAA0F3C&0&00E0"`
  or reboot. Keep the Focusrite on an **Intel-controller port**, not the ASMedia 10 Gbps ones;
  consider disabling USB selective suspend. Cause unproven: ASMedia flakiness and/or Claude
  force-killing the rig mid-stream several times that night.

## Relaunching the rig (for Claude)

- **Never `Stop-Process` a running rig.** Create `rig/restart.flag` (clean restart, keeps input) or
  `rig/quit.flag` (clean quit); the main loop checks every 50 ms and closes the ASIO stream properly.
  Stale flags are cleared at startup. Only launch a new rig when no `python` rig process is running.
- Launch: `Start-Process "rig\Guitar Rig.bat" -ArgumentList "--input-channel 2"` (opens its own console).

## Verified vs. not

- Verified offline: all presets run (<2% CPU budget), level matching, tuner accuracy
  (0.0 cents on exact tones), tunings, scale maps and bend detection, full `main()` with fake audio/keys.
- **Not yet verified by ear on the real guitar:** the reworked Hendrix preset and the added
  "oomph" (cab low-end bump + power-amp stage). Ask Omar how they sound.
- **NAM amps (2026-10-03):** presets 1–4 now use real amp captures via the TONE3000 plugin.
  Verified offline: each preset plays its capture, levels within ~1.5 dB of each other and Clean,
  preset switching OK, <10% CPU at a 64-sample buffer. **Not yet heard on the real guitar.**
- **Heard on the real guitar (2026-10-03/04):** "sounds awesome" with NAM amps. Presets 5–9 and `d`
  are newer; ask how they sound.
- **Restart flag verified live 2026-10-05** (`rig/restart.flag` → clean exit, bat relaunched).
  **Quit flag verified live 2026-10-11** (exited within 4 s, flag consumed).
- **2026-10-11 output dropout, unresolved:** after ~12.5 h running, guitar output went silent while the
  Scarlett and the rig's meters still showed signal; the rig was still using ~8% CPU, the Focusrite was
  OK in Windows, and the system log had no errors. Omar's checks didn't fix it, so the rig was shut down
  via `quit.flag`. Cause unknown; maybe the ASIO output stalls on long runs (cf. the 8 h ASMedia crash).
  Also: 2026-10-10 11:41 another 0x1A MEMORY_MANAGEMENT bugcheck (same 0x1230 arg as 2026-10-06); suggested `mdsched`.
- **Auto-wah (2026-10-05):** `w` on/off, `e` sensitivity low/med/high. `AutoWah` in rig.py sits after the
  input HPF, in front of every preset: envelope follower (4 ms attack / 150 ms release) sweeping a
  `LadderFilter` BPF12 (res 0.6) 350–2400 Hz, retuned every 32 samples so the buffer size doesn't matter.
  Offline: identical output at block sizes 32–512, clean 10 ms on/off fade, ~1% CPU, level 0 to +3 dB
  through the presets. **Not yet heard on the real guitar** — sweep range/sensitivity may need tuning by ear.
- **Record timeout, fixed live 2026-10-05:** its polling loop replaced `sd.wait()`, which also *closed* the
  recording stream; left open, it held the single-client ASIO driver, so the main stream failed with
  "Device unavailable [-9985]". `record()` now calls `sd.stop()` after the loop. Rig ran fine after.
- **Untested:** cab IR loading from a real IR file (tested with a synthetic IR only).

## Next steps

0. Omar is rebooting (ASMedia controller crash). After: check `Get-PnpDevice -PresentOnly` shows
   "Analogue 1 + 2 (... Focusrite USB Audio)" and "Scarlett Solo USB", then launch the rig.
1. Ask how presets 5–9 and `d` (Derek Trucks) sound; tune by ear. Spare captures: 20 Super Reverb
   settings + 3 Plexi in `rig/nam/captures/`.
2. Optional cab IRs → `rig/irs/<Preset>.wav` or `rig/irs/default.wav`.
3. Ideas Omar liked: more players (Albert Collins, Peter Green, T-Bone Walker, Buddy Guy); a Fender
   Bassman capture for Buddy Guy / Muddy; make `--input-channel 2` the launcher default + desktop shortcut.
4. **Portability (Omar asked 2026-10-04):** replace the laptop with a Raspberry Pi 5-type box.
   Discussed: Pi 5 + the Scarlett Solo (class-compliant) or a Hi-Z audio HAT (e.g. Pisound); NAM on
   Linux via NAM core / LV2 (pedalboard can't host LV2, and the TONE3000 VST3 is Windows/mac only),
   lighter/slimmed models for CPU; or an off-the-shelf NAM box (e.g. MOD Dwarf) / open-source Pi-Stomp.
   Not started; needs a decision from Omar.

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
  A stale `OneDrive\Desktop\Guitar Rig.bat` (from that copy) launches the old rig or fails. Both should be
  deleted (asked 2026-10-17; the delete was blocked by the permission check, pending Omar).
- Shortcuts (2026-10-14): `Guitar Rig.lnk` in the Start menu and on `OneDrive\Desktop` →
  `cmd.exe /c "...\rig\Guitar Rig.bat" --input-channel 2`. Start-search right-click lacks "Pin to taskbar";
  pin the desktop one via drag or Show more options.
- 2026-10-19: the Scarlett is still plugged into an **ASMedia** port (root hub under the ASMedia controller), not Intel.
  Windows audio was buggy after a rig quit; all USB controllers reported OK. Claude's shell isn't admin, so a
  controller reset (`pnputil /restart-device`) needs Omar at the PC for the UAC prompt.
- 2026-10-20: **ASMedia controller crashed again** (Device Manager: Error), second time after 10-04. The Scarlett
  dropped out entirely and the rig process had exited. Replugging into the same port didn't bring it back.
  The elevated `pnputil /restart-device` brought the controller back to OK, but the Scarlett still didn't reappear
  (20 s wait). By 2026-10-24 the controller was in Error again, so Omar rebooted (last boot before that: 10-18).
- Running the reset from Claude's non-admin shell: `Start-Process powershell -Verb RunAs` plus `-EncodedCommand`
  (base64 UTF-16). Passing the command as plain `-Command` args fails (exit 1) because the `&`s in the instance
  ID break apart. Omar has to click the UAC prompt.
- Port options (unresolved): Omar says the PC has **only one USB-C port** (the ASMedia one) and "we tried USB once
  and it sucked". Suggested a USB-C-to-A cable into an Intel USB-A port (the Scarlett is USB 2.0, and the bad
  result may date from the WASAPI days), or the **NVIDIA USB 3.10 controller** (probably a USB-C port on the GPU).
  Neither tried yet.
- If `Guitar Rig.bat` is left sitting at `pause` after a quit, it's safe to close: it holds no audio stream.
  Restart options given to Omar: `x` in the rig, `q` + shortcut, or ask Claude (flags). There are no voice commands;
  Windows Voice Access ("open Guitar Rig", "press x") was suggested but not tested.
- An automatic feedback-detector was tried and removed: it couldn't tell a howl from sustained fuzz.
- Long bash heredocs with mixed `'''` quoting got mangled once; prefer the Edit tool for multi-line patches.
