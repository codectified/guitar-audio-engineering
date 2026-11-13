#!/bin/bash
# Double-click launcher for macOS (the Mac twin of "Guitar Rig.bat")
cd "$(dirname "$0")"
VENV=../.venv
if [ ! -x "$VENV/bin/python" ]; then
    echo "First run: setting up Python packages..."
    python3 -m venv "$VENV" && "$VENV/bin/pip" install -q -r ../requirements.txt || { read -p "Setup failed. Press Enter to close."; exit 1; }
fi
device_here() { "$VENV/bin/python" -c 'import sounddevice as sd, sys
sys.exit(not any(n in d["name"] for d in sd.query_devices() for n in ("Spark", "Scarlett")))' 2>/dev/null; }
ARGS=("$@")
while true; do
    "$VENV/bin/python" rig.py "${ARGS[@]}"
    code=$?
    # rig.py exits with 11/12 when you press x: restart on input 1/2 without the strum check
    if [ $code -eq 11 ]; then ARGS=("$@" --input-channel 1)
    elif [ $code -eq 12 ]; then ARGS=("$@" --input-channel 2)
    elif [ $code -eq 13 ] || { [ $code -ne 0 ] && ! device_here; }; then
        # 13 = the interface went away mid-session (Spark switched off, Bluetooth took it): wait, then carry on
        echo "Waiting for the Spark GO / Scarlett to come back (switch it on; close this window to give up)..."
        until device_here; do sleep 3; done
        sleep 3  # give Core Audio a moment to finish setting it up
    else break; fi
done
read -p "Press Enter to close."
