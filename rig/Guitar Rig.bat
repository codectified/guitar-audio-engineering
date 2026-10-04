@echo off
cd /d "%~dp0"
set "ARGS=%*"
:start
python rig.py %ARGS%
rem rig.py exits with 11/12 when you press x: restart on input 1/2 without the strum check
if %errorlevel%==11 (set "ARGS=%* --input-channel 1" & goto start)
if %errorlevel%==12 (set "ARGS=%* --input-channel 2" & goto start)
pause
