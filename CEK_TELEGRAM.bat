@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 telegram_main.py --check
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python tidak ditemukan. Pasang Python 3 dan coba lagi.
    pause
    exit /b 1
  )
  python telegram_main.py --check
)
set TELEGRAM_EXIT_CODE=%ERRORLEVEL%
echo.
pause
exit /b %TELEGRAM_EXIT_CODE%
