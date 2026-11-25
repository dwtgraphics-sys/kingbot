@echo off
rem ===========================================================================
rem  Run once as administrator: switch Kingbot to a console-free process.
rem
rem  1. stops every running bot (console version)
rem  2. registers the logon + watchdog tasks
rem  3. starts the bot hidden with pythonw
rem ===========================================================================
setlocal
cd /d "%~dp0"

echo 1) stopping the console version ...
taskkill /f /im python.exe >nul 2>&1
taskkill /f /im pythonw.exe >nul 2>&1
timeout /t 4 /nobreak >nul

echo 2) registering the tasks ...
call "%~dp0install_tasks.bat"

echo 3) starting the bot hidden ...
wscript.exe //B "%~dp0start_bot_hidden.vbs"
timeout /t 8 /nobreak >nul

>>"%~dp0launcher.log" echo [%DATE% %TIME%] switched to the hidden (console-free) runner
exit /b 0
