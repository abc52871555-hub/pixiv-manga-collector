@echo off
title Pixiv Manga Collector
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo Python was not found. Please install Python 3.9 or newer
  echo and enable "Add Python to PATH" during installation.
  echo Download: https://www.python.org/downloads/
  echo.
  pause
  exit /b 1
)

python -c "import requests" >nul 2>nul
if errorlevel 1 (
  echo Installing dependency: requests ...
  python -m pip install requests
)

python -c "import PIL" >nul 2>nul
if errorlevel 1 (
  echo.
  echo Optional: install Pillow to enable LSB/Alpha metadata deep scan:
  echo   python -m pip install pillow
  echo.
)

python -c "import webview" >nul 2>nul
if errorlevel 1 (
  echo.
  echo Optional: install pywebview to enable one-click Pixiv login window:
  echo   python -m pip install pywebview
  echo.
)

echo.
echo Starting Pixiv Manga Collector at http://127.0.0.1:8765
echo The browser should open automatically.
echo Close this window to stop the server.
echo.
python server.py --open
if errorlevel 1 pause
