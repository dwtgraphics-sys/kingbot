@echo off
rem SEC-04: build the protected Kingbot application (Kingbot.exe). Run on the server / build PC.
setlocal
cd /d "%~dp0\.."
where python >nul 2>&1 || (echo Python not found in PATH. & pause & exit /b 1)
echo Installing the build tool (PyInstaller) if needed ...
python -m pip install --quiet --upgrade pyinstaller || (echo pip failed & pause & exit /b 1)
python packaging\build_protected.py
echo.
pause
