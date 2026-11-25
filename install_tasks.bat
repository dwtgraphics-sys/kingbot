@echo off
rem ===========================================================================
rem  Run once as administrator.
rem
rem  Registers two tasks:
rem    Kingbot          at logon, highest rights  -> starts the bot hidden (pythonw, no console)
rem    Kingbot watchdog every 2 minutes, hidden   -> starts the bot again if it is not running
rem
rem  With the bot running without a console it survives Remote Desktop disconnects,
rem  which is what kept killing it before.
rem ===========================================================================
setlocal
cd /d "%~dp0"

schtasks /delete /tn "Kingbot" /f >nul 2>&1
schtasks /create /tn "Kingbot" /tr "wscript.exe //B \"%~dp0start_bot_hidden.vbs\"" /sc onlogon /rl highest /f
set RC1=%ERRORLEVEL%

schtasks /delete /tn "Kingbot watchdog" /f >nul 2>&1
schtasks /create /tn "Kingbot watchdog" /tr "wscript.exe //B \"%~dp0watchdog_hidden.vbs\"" /sc minute /mo 2 /rl highest /f
set RC2=%ERRORLEVEL%

>>"%~dp0launcher.log" echo [%DATE% %TIME%] tasks install: Kingbot rc=%RC1%, watchdog rc=%RC2%
echo.
schtasks /query /tn "Kingbot" /fo LIST | findstr /i "TaskName Status"
schtasks /query /tn "Kingbot watchdog" /fo LIST | findstr /i "TaskName Status"
echo.
echo Done (Kingbot=%RC1%, watchdog=%RC2%). You can close this window.
timeout /t 20
exit /b 0
