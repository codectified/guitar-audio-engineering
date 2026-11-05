#!/bin/bash
# Double-click launcher for macOS (the Mac twin of "Guitar Rig.bat")
cd "$(dirname "$0")"
VENV=../.venv
if [ ! -x "$VENV/bin/python" ]; then
    echo "First run: setting up Python packages..."
    python3 -m venv "$VENV" && "$VENV/bin/pip" install -q -r ../requirements.txt || { read -p "Setup failed. Press Enter to close."; exit 1; }
fi
ARGS=("$@")
while true; do
    "$VENV/bin/python" rig.py "${ARGS[@]}"
    code=$?
    # rig.py exits with 11/12 when you press x: restart on input 1/2 without the strum check
    if [ $code -eq 11 ]; then ARGS=("$@" --input-channel 1)
    elif [ $code -eq 12 ]; then ARGS=("$@" --input-channel 2)
    else break; fi
done
read -p "Press Enter to close."
