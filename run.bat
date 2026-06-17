@echo off
REM Start the bot. Reads config.yaml + .env.
REM Stays in dry-run until you set  dry_run: false  in config.yaml.
cd /d "%~dp0"
if not exist .venv\Scripts\activate.bat (
  echo [X] Not set up yet - double-click setup_windows.bat first.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
python main.py
echo.
echo (bot stopped)
pause
