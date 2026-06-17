@echo off
REM Read-only broker check: connection, gold symbol, live price, sizing.
REM Places NO orders. Run this before run.bat.
cd /d "%~dp0"
if not exist .venv\Scripts\activate.bat (
  echo [X] Not set up yet - double-click setup_windows.bat first.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python tools\mt5_check.py
echo.
pause
