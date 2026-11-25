@echo off
rem ===========================================================================
rem  Kingbot watchdog - started by Task Scheduler every 2 minutes (hidden).
rem
rem  Starts the bot with pythonw (no console window) when it is not running.
rem  The console version died whenever Remote Desktop disconnected, because the
rem  session's window was destroyed together with python.
rem ===========================================================================
setlocal
cd /d "%~dp0"

rem pythonw runs the bot without a console; python.exe would open one.
tasklist /fi "IMAGENAME eq pythonw.exe" /fo csv /nh 2>nul | find /i "pythonw.exe" >nul
if not errorlevel 1 exit /b 0
tasklist /fi "IMAGENAME eq python.exe" /fo csv /nh 2>nul | find /i "python.exe" >nul
if not errorlevel 1 exit /b 0

>>"%~dp0launcher.log" echo [%DATE% %TIME%] watchdog: the bot is not running - starting it (hidden)
wscript.exe //B "%~dp0start_bot_hidden.vbs"
exit /b 0
