@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 whatsapp_main.py --check
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python tidak ditemukan. Pasang Python 3 dan coba lagi.
    pause
    exit /b 1
  )
  python whatsapp_main.py --check
)
set WHATSAPP_EXIT_CODE=%ERRORLEVEL%
echo.
pause
exit /b %WHATSAPP_EXIT_CODE%
