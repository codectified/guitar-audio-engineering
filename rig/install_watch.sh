#!/bin/bash
# Start (or with --remove, stop) opening the rig automatically when the Spark GO is switched on.
PLIST=~/Library/LaunchAgents/com.guitarrig.sparkwatch.plist
launchctl bootout "gui/$(id -u)" "$PLIST" 2>/dev/null
if [ "$1" = "--remove" ]; then rm -f "$PLIST"; echo "Auto-launch removed."; exit; fi
WATCH="$(cd "$(dirname "$0")" && pwd)/spark_watch.sh"
cat > "$PLIST" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>com.guitarrig.sparkwatch</string>
  <key>ProgramArguments</key><array><string>/bin/bash</string><string>$WATCH</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
</dict></plist>
PL
launchctl bootstrap "gui/$(id -u)" "$PLIST" && echo "Auto-launch on: the rig opens when the Spark GO is switched on."
