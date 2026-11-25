@echo off
rem ===========================================================================
rem  Restart the game client (it froze at 13:20: Unity's crash handler was up,
rem  the window kept showing one frozen frame and ignored every click).
rem  Run this as administrator.
rem ===========================================================================
setlocal
cd /d "%~dp0"

echo Closing the game client ...
taskkill /f /im MASS.exe >nul 2>&1
taskkill /f /im UnityCrashHandler64.exe >nul 2>&1
timeout /t 5 /nobreak >nul

echo Starting Rise of Kingdoms ...
start "" "C:\Users\Public\Desktop\Rise of Kingdoms.lnk"
timeout /t 25 /nobreak >nul

>>"%~dp0launcher.log" echo [%DATE% %TIME%] game restart: client closed and started again
echo Done.
exit /b 0
