@echo off
rem Jalankan file ini SEKALI SAJA (cukup dobel-klik biasa, tidak perlu Run as
rem Administrator kecuali muncul pesan gagal di bawah). Setelah ini, Telegram
rem Bot otomatis jalan diam-diam setiap kali Anda login Windows -- tidak perlu
rem lagi buka JALANKAN_TELEGRAM.bat manual.
setlocal
cd /d "%~dp0"

echo Mendaftarkan Telegram Bot ke Task Scheduler Windows...
schtasks /create /tn "TaqiAI_TelegramBot" /tr "wscript.exe \"%~dp0JALANKAN_TELEGRAM_HIDDEN.vbs\"" /sc onlogon /rl limited /f

if errorlevel 1 (
  echo.
  echo GAGAL mendaftarkan. Coba klik kanan file ini, pilih "Run as administrator", lalu jalankan lagi.
  pause
  exit /b 1
)

echo.
echo BERHASIL. Mulai sekarang Telegram Bot otomatis jalan setiap kali Anda login Windows,
echo tanpa jendela terminal yang perlu dibuka manual.
echo.
set /p JALANKAN_SEKARANG="Mau langsung dicoba sekarang juga tanpa logout/restart dulu? (Y/N): "
if /i "%JALANKAN_SEKARANG%"=="Y" (
  wscript.exe "%~dp0JALANKAN_TELEGRAM_HIDDEN.vbs"
  echo Sudah dijalankan di background. Coba kirim /status ke bot Telegram Anda dari HP/PC.
  echo Kalau tidak ada balasan dalam beberapa detik, cek logs\telegram_background.log untuk error.
)
echo.
pause
