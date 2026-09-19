@echo off
rem Menghentikan proses Telegram Bot yang sedang jalan diam-diam di background
rem (dimulai lewat JALANKAN_TELEGRAM_HIDDEN.vbs / auto-start). Tidak menghapus
rem pendaftaran auto-start -- kalau Anda login ulang, bot akan jalan lagi.
rem Pakai HAPUS_AUTOSTART_TELEGRAM.bat kalau mau auto-start-nya benar-benar dimatikan.
echo Menghentikan proses Telegram Bot (python telegram_main.py) yang jalan di background...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*telegram_main.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host ('Dihentikan: PID ' + $_.ProcessId) }"
echo Selesai. Kalau tidak ada baris "Dihentikan" di atas, berarti memang tidak ada proses yang jalan.
pause
