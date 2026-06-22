@echo off
REM Lists the Telegram channels your account is in, with their numeric ids.
REM Use this to find the exact source_channel for config.yaml.
REM Close run.bat first so they don't share the session file.
cd /d "%~dp0"
if not exist .venv\Scripts\activate.bat (
  echo [X] Not set up yet - double-click setup_windows.bat first.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python tools\list_channels.py
echo.
pause
