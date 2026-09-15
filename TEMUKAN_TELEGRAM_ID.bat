@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher ^(py^) tidak ditemukan.
  echo Pasang Python 3 terlebih dahulu lalu coba lagi.
  pause
  exit /b 1
)

py -3 telegram_main.py --discover-admin
set ERR=%ERRORLEVEL%
echo.
pause
exit /b %ERR%
