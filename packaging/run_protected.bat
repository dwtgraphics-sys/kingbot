@echo off
rem ===========================================================================
rem  SEC-04: launcher for the PROTECTED Kingbot build (Kingbot.exe).
rem  Same restart rules as 3_start_bot.bat, but it runs the packaged exe:
rem    exit 3 -> restart   exit 0 -> stop on purpose   other -> crashed (retry a few times)
rem  Runtime files live in the runtime\ folder next to the exe (KINGBOT_HOME),
rem  so rebuilding the exe never touches settings, state or logs.
rem  Usage:  run_protected.bat        normal start (asks for administrator rights)
rem          run_protected.bat auto   started by the watchdog task: never waits for a key
rem ===========================================================================
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Kingbot (protected)

set "AUTO="
if /i "%~1"=="auto" set "AUTO=1"

set "EXE=%~dp0Kingbot.exe"
set "KINGBOT_HOME=%~dp0runtime"
set "FAST_WAIT=5"
set "CRASH_WAIT=30"
set "HEALTHY_RUN=180"
set "MAX_CRASHES=3"
set "MAX_FAST_FAILS=5"
set "LAUNCH_LOG=%KINGBOT_HOME%\launcher.log"

if not exist "%EXE%" (
  echo Kingbot.exe is not here. Build it first with build_protected.bat.
  if not defined AUTO pause
  exit /b 1
)
if not exist "%KINGBOT_HOME%" mkdir "%KINGBOT_HOME%"

rem the game runs elevated, so the bot must too or its clicks are ignored
net session >nul 2>&1
if not errorlevel 1 goto admin_ok
if defined KINGBOT_ELEVATING goto admin_ok
if defined AUTO ( >>"%LAUNCH_LOG%" echo [%DATE% %TIME%] not administrator ^(auto^) & exit /b 1 )
set "KINGBOT_ELEVATING=1"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs" >nul 2>&1
exit /b 0
:admin_ok

set /a CRASHES=0
set /a FAST_FAILS=0
:loop
>>"%LAUNCH_LOG%" echo [%DATE% %TIME%] start Kingbot.exe
"%EXE%"
set "RC=%ERRORLEVEL%"
>>"%LAUNCH_LOG%" echo [%DATE% %TIME%] exit code !RC!
if "!RC!"=="0" ( echo Kingbot stopped on purpose. & if not defined AUTO pause & exit /b 0 )
if "!RC!"=="3" (
  >>"%LAUNCH_LOG%" echo [%DATE% %TIME%] restarting in %FAST_WAIT%s
  timeout /t %FAST_WAIT% /nobreak >nul 2>&1
  goto loop
)
set /a CRASHES+=1
if !CRASHES! gtr %MAX_CRASHES% (
  >>"%LAUNCH_LOG%" echo [%DATE% %TIME%] giving up after !CRASHES! failed starts ^(code !RC!^)
  echo Kingbot failed to start !CRASHES! times - see runtime\log.txt.
  if not defined AUTO pause
  exit /b 1
)
>>"%LAUNCH_LOG%" echo [%DATE% %TIME%] crash - retry in %CRASH_WAIT%s ^(!CRASHES! of %MAX_CRASHES%^)
timeout /t %CRASH_WAIT% /nobreak >nul 2>&1
goto loop
