@echo off
rem Membatalkan pendaftaran auto-start (kebalikan dari SETUP_AUTOSTART_TELEGRAM.bat).
rem Setelah ini, Telegram Bot TIDAK LAGI otomatis jalan saat login -- kembali
rem seperti semula, harus dobel-klik JALANKAN_TELEGRAM.bat manual.
schtasks /delete /tn "TaqiAI_TelegramBot" /f
echo.
echo Auto-start Telegram Bot sudah dinonaktifkan.
echo Kalau prosesnya masih jalan sekarang (belum logout/restart), jalankan
echo HENTIKAN_TELEGRAM_BACKGROUND.bat juga untuk menghentikannya sepenuhnya.
pause
