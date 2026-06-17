@echo off
REM One-time setup on Windows. Double-click this file.
cd /d "%~dp0"
echo ============================================
echo   gold-signal-bot  -  Windows setup
echo ============================================
echo.

where py >nul 2>nul
if errorlevel 1 (
  echo [X] Python not found.
  echo     Install Python 3.11+ from https://www.python.org/downloads/
  echo     IMPORTANT: tick "Add python.exe to PATH" during install, then re-run this.
  pause
  exit /b 1
)

echo [1/3] Creating virtual environment (.venv) ...
py -3 -m venv .venv

echo [2/3] Upgrading pip ...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip

echo [3/3] Installing dependencies (telethon, MetaTrader5, PyYAML) ...
python -m pip install -r requirements.txt

echo.
echo ============================================
echo   Setup complete.
echo ============================================
echo Next steps:
echo   1. Open the  .env  file and fill in TG_API_ID and TG_API_HASH
echo      (get them at https://my.telegram.org  ^>  API development tools)
echo   2. Make sure MetaTrader 5 is open, logged into the demo account,
echo      and "Algo Trading" is ON (toolbar button must NOT be red).
echo   3. Double-click  check.bat   to verify the broker connection.
echo   4. Double-click  run.bat     to start the bot.
echo.
pause
