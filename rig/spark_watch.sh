#!/bin/bash
# Opens the rig whenever the Spark GO shows up (switched on / plugged in) and no rig window is open.
# Runs in the background from ~/Library/LaunchAgents/com.guitarrig.sparkwatch.plist (see install_watch.sh).
cd "$(dirname "$0")"
PY=../.venv/bin/python
here() { "$PY" -c 'import sounddevice as sd, sys; sys.exit(not any("Spark" in d["name"] for d in sd.query_devices()))' 2>/dev/null; }
was_here=false
while true; do
    if pgrep -f "Guitar Rig.command" >/dev/null; then
        was_here=true  # a rig window is open (playing, or waiting for the Spark itself): leave it alone
    elif here; then
        # only on the moment it appears, so quitting with q doesn't relaunch while the Spark stays on
        $was_here || { sleep 3; open "Guitar Rig.command"; sleep 10; }
        was_here=true
    else
        was_here=false
    fi
    sleep 3
done
