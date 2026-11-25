@echo off
rem ===========================================================================
rem  Kingbot watchdog - started by Task Scheduler every 2 minutes (hidden, via watchdog.vbs).
rem  v193: the work is done by watchdog.ps1:
rem    - starts the bot when it is not running (found by kingbot.pid / bot.py, not "any pythonw":
rem      stream_bot.py also runs with pythonw and hid a dead bot before)
rem    - restarts the bot when it is frozen (heartbeat.txt older than 5 minutes)
rem  A frozen GAME is handled inside the bot (closed after 3 minutes "Not Responding").
rem ===========================================================================
setlocal
cd /d "%~dp0"
powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0watchdog.ps1"
exit /b 0
