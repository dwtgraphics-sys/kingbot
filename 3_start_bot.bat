@echo off
rem ===========================================================================
rem  Kingbot launcher  -  C:\RisBot\3_start_bot.bat
rem
rem  Usage:  3_start_bot.bat           normal start (asks for administrator rights)
rem          3_start_bot.bat auto      start by the watchdog task: never waits for a key
rem
rem  What bot.py means when it exits:
rem    code 3  -> "restart me"  (self-update, new version found, stuck-window rescue)
rem    code 0  -> stopped on purpose (F12, or the mouse pushed into a corner)
rem    other   -> crashed
rem
rem  The launcher restarts on 3, stays stopped on 0, retries a crash a few times
rem  and gives up instead of looping forever. Every start and exit goes to
rem  launcher.log so a failure can be explained later.
rem ===========================================================================
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Kingbot

rem v159: "auto" = started by the watchdog task. It must never stop and wait for a
rem key, because nobody is looking at that window.
set "AUTO="
if /i "%~1"=="auto" set "AUTO=1"

set "SCRIPT=bot.py"
set "FAST_WAIT=5"
set "CRASH_WAIT=30"
set "HEALTHY_RUN=180"
set "MAX_CRASHES=3"
set "MAX_FAST_FAILS=5"
set "LAUNCH_LOG=%~dp0launcher.log"

call :log "launcher started (auto=%AUTO%)"

rem --- only one Kingbot at a time: two copies would fight over the mouse -----
tasklist /v /fi "IMAGENAME eq python.exe" /fo csv /nh 2>nul | find /i "Kingbot" >nul
if not errorlevel 1 (
  echo Kingbot is already running - close that window first.
  call :log "refused: another Kingbot window is already running"
  call :pause_or_exit
  exit /b 1
)

rem --- the game runs elevated, so Kingbot must too or its clicks are ignored --
net session >nul 2>&1
if not errorlevel 1 goto :admin_ok
if defined KINGBOT_ELEVATING goto :admin_ok
if defined AUTO (
  call :log "not administrator - the watchdog task must run with highest privileges"
  exit /b 1
)
echo Asking Windows for administrator rights - approve the prompt to continue ...
set "KINGBOT_ELEVATING=1"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs" >nul 2>&1
if errorlevel 1 (
  echo Could not get administrator rights.
  echo Right-click this file and choose "Run as administrator" instead.
  call :log "elevation failed"
  call :pause_or_exit
  exit /b 1
)
call :log "relaunched with administrator rights"
exit /b 0
:admin_ok

rem --- python ---------------------------------------------------------------
rem "python" from PATH first, then a normal Windows install, then a per-user
rem install. The "py" launcher is deliberately not used: without a real Python
rem it can open a window and never return, which would freeze the launcher.
set "PY="
where python >nul 2>&1
if not errorlevel 1 set "PY=python"
if not defined PY for /d %%d in ("%ProgramFiles%\Python3*") do if exist "%%~fd\python.exe" set "PY=%%~fd\python.exe"
if not defined PY for /d %%d in ("%LocalAppData%\Programs\Python\Python3*") do if exist "%%~fd\python.exe" set "PY=%%~fd\python.exe"
if not defined PY (
  echo Python is not installed, or it is not where this launcher can find it.
  call :log "python not found"
  call :pause_or_exit
  exit /b 1
)
"%PY%" --version >nul 2>&1
if errorlevel 1 (
  echo Python was found at "%PY%" but it does not run.
  call :log "python did not run: %PY%"
  call :pause_or_exit
  exit /b 1
)
call :log "python: %PY%"

set /a CRASHES=0
set /a FAST_FAILS=0

:loop
call :now T_START
call :log "start %SCRIPT%"
"%PY%" %SCRIPT%
set "RC=%ERRORLEVEL%"
call :now T_END
set /a RAN=T_END-T_START
if %RAN% lss 0 set /a RAN+=86400
call :log "exit code %RC% after %RAN%s"

if "%RC%"=="3" goto restart
if "%RC%"=="0" goto stopped
goto crash

:stopped
call :log "stopped on purpose"
echo.
echo Kingbot stopped. F12 or moving the mouse into a corner ends it like this.
echo This window stays open - close it whenever you like.
call :pause_or_exit
exit /b 0

:restart
rem the bot asked for a restart: update, new version, or stuck-window rescue
if %RAN% geq 60 (
  set /a FAST_FAILS=0
) else (
  set /a FAST_FAILS+=1
)
if !FAST_FAILS! gtr %MAX_FAST_FAILS% (
  call :log "too many quick restarts - giving up"
  echo.
  echo Kingbot keeps asking for a restart seconds after starting.
  echo The reason is in the last lines of log.txt. Start this file again when fixed.
  call :pause_or_exit
  exit /b 1
)
call :log "restarting in %FAST_WAIT%s"
call :wait %FAST_WAIT%
goto loop

:crash
if %RAN% geq %HEALTHY_RUN% set /a CRASHES=0
set /a CRASHES+=1
if !CRASHES! gtr %MAX_CRASHES% (
  call :log "giving up after %CRASHES% failed starts"
  echo.
  echo Kingbot failed to start %CRASHES% times in a row - last exit code %RC%.
  echo The reason is usually in the last lines of log.txt.
  call :pause_or_exit
  exit /b 1
)
call :log "crash - retrying in %CRASH_WAIT%s (failure %CRASHES% of %MAX_CRASHES%)"
echo.
echo Kingbot exited with code %RC% - restarting in %CRASH_WAIT% seconds ^(failure %CRASHES% of %MAX_CRASHES%^).
call :wait %CRASH_WAIT%
goto loop

rem ---------------------------------------------------------------------------
:pause_or_exit
rem in auto mode nobody is watching this window: never block here
if defined AUTO exit /b 0
echo.
pause
goto :eof

:wait
rem wait %1 seconds - also works when stdin is redirected (timeout alone fails)
timeout /t %1 /nobreak >nul 2>&1
if errorlevel 1 (
  set /a PINGS=%1+1
  ping -n !PINGS! 127.0.0.1 >nul 2>&1
)
goto :eof

:now
rem seconds since midnight, stored in the variable named by %1
for /f "tokens=1-4 delims=:., " %%a in ("%TIME%") do (
  set "HH=%%a"
  set "MM=%%b"
  set "SS=%%c"
)
call :num HH
call :num MM
call :num SS
set /a %1=HH*3600+MM*60+SS 2>nul
goto :eof

:num
rem normalise one clock field in place: drop a leading zero, keep a digit
set "V=!%~1!"
if "!V:~0,1!"=="0" set "V=!V:~1!"
if "!V!"=="" set "V=0"
set "%~1=!V!"
goto :eof

:log
>>"%LAUNCH_LOG%" echo [%DATE% %TIME%] %~1
goto :eof
