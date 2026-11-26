@echo off
rem ===========================================================================
rem  SEC-04: run the protected Kingbot build in the background as a scheduled task
rem  that starts at logon and is kept alive. Uses Windows Task Scheduler (no extra
rem  software). Run this once, as administrator, from inside dist\Kingbot\.
rem    install_service.bat            install / update the task
rem    install_service.bat remove     delete the task
rem  The task runs run_protected.bat auto, which restarts the exe on exit code 3
rem  and after a crash, exactly like the foreground launcher.
rem ===========================================================================
setlocal EnableExtensions
cd /d "%~dp0"
set "TASK=Kingbot"
set "RUNNER=%~dp0run_protected.bat"

net session >nul 2>&1 || (echo Run this as administrator ^(right-click ^> Run as administrator^). & pause & exit /b 1)

if /i "%~1"=="remove" (
  schtasks /delete /tn "%TASK%" /f
  echo Removed the %TASK% background task.
  pause & exit /b 0
)

if not exist "%RUNNER%" (echo run_protected.bat is not next to this file. & pause & exit /b 1)

rem highest privileges (the game is elevated), start at logon, restart if it ever stops
schtasks /create /tn "%TASK%" /tr "\"%RUNNER%\" auto" /sc onlogon /rl highest /f
if errorlevel 1 (echo Could not create the task. & pause & exit /b 1)
echo.
echo Installed. Kingbot will start automatically at logon and keep running in the background.
echo Start it now:   schtasks /run /tn "%TASK%"
echo Stop it:        schtasks /end /tn "%TASK%"
echo Remove it:      install_service.bat remove
pause
