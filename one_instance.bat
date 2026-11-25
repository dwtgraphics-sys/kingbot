@echo off
rem ===========================================================================
rem  Kill every running Kingbot instance and start exactly one.
rem  (Two copies appeared at 15:19 because the watchdog started a second one
rem   while the first was still working - two bots fight over the mouse.)
rem  Run this as administrator.
rem ===========================================================================
setlocal
cd /d "%~dp0"

echo Stopping every python instance ...
taskkill /f /im python.exe >nul 2>&1
timeout /t 4 /nobreak >nul

>>"%~dp0launcher.log" echo [%DATE% %TIME%] cleanup: all bot instances stopped, starting one
start "" "%~dp03_start_bot.bat" auto
exit /b 0
