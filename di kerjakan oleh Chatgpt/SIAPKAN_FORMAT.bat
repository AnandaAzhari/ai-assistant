@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
echo Menyiapkan Python terpisah dalam folder percobaan ini.
echo Paket pypdf diperlukan untuk watermark PDF hasil konversi Word.
echo Microsoft Word desktop harus sudah terpasang.
if exist ".venv\Scripts\python.exe" goto install
py -3 -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if not errorlevel 1 (
    py -3 -m venv ".venv"
) else (
    python -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
    if errorlevel 1 (
        echo Python 3.11 atau lebih baru tidak ditemukan.
        pause
        exit /b 1
    )
    python -m venv ".venv"
)
if not exist ".venv\Scripts\python.exe" (
    echo Gagal menyiapkan Python percobaan.
    pause
    exit /b 1
)
:install
".venv\Scripts\python.exe" -m pip install -r requirements_format.txt
if errorlevel 1 (
    echo Pemasangan paket gagal. Periksa koneksi internet dan pesan di atas.
    pause
    exit /b 1
)
echo Selesai. Buka JALANKAN_CONTOH_ANTREAN.bat untuk mencoba format terbaru.
pause
