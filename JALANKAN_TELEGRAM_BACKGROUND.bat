@echo off
rem Versi non-interaktif dari JALANKAN_TELEGRAM.bat, khusus dipakai lewat
rem Task Scheduler (lihat SETUP_AUTOSTART_TELEGRAM.bat). Tidak ada "pause"
rem di sini supaya tidak menggantung diam-diam kalau dijalankan tanpa
rem jendela terlihat -- semua output (termasuk error) ditulis ke
rem logs\telegram_background.log supaya tetap bisa diperiksa.
setlocal
cd /d "%~dp0"
if not exist logs mkdir logs

where py >nul 2>nul
if not errorlevel 1 (
  py -3 telegram_main.py >> logs\telegram_background.log 2>&1
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo [%date% %time%] Python tidak ditemukan. Pasang Python 3 dan coba lagi. >> logs\telegram_background.log
    exit /b 1
  )
  python telegram_main.py >> logs\telegram_background.log 2>&1
)
exit /b %ERRORLEVEL%
