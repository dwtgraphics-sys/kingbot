@echo off
rem ===========================================================================
rem  Run this once as administrator: registers the Kingbot watchdog task.
rem
rem  The task checks every 2 minutes whether the bot is running and starts it if
rem  not. It runs through wscript + watchdog.vbs so NO console window appears -
rem  a visible console steals the focus from the game and every click then lands
rem  in the wrong window (that is what happened at 12:58).
rem ===========================================================================
setlocal
cd /d "%~dp0"

schtasks /delete /tn "Kingbot watchdog" /f >nul 2>&1
schtasks /create /tn "Kingbot watchdog" /tr "wscript.exe \"%~dp0watchdog.vbs\"" /sc minute /mo 2 /rl highest /f
set RC=%ERRORLEVEL%
>>"%~dp0launcher.log" echo [%DATE% %TIME%] watchdog task install (hidden): rc=%RC%
echo.
schtasks /query /tn "Kingbot watchdog" /fo LIST | findstr /i "TaskName Status Next Task"
echo.
echo Done (rc=%RC%). You can close this window.
timeout /t 15
exit /b %RC%
