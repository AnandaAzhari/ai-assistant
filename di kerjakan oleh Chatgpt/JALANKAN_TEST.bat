@echo off
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONUTF8=1"
py -3 -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
if not errorlevel 1 (
    set "BILLING_PY=py -3"
) else (
    python -c "import sys; sys.exit(sys.version_info < (3, 11))" >nul 2>&1
    if errorlevel 1 (
        echo Python 3.11 atau lebih baru belum ditemukan.
        pause
        exit /b 1
    )
    set "BILLING_PY=python"
)
%BILLING_PY% -B -X utf8 -m unittest discover -s tests -p "test_*.py" -v
set "BILLING_EXIT=%ERRORLEVEL%"
echo.
if "%BILLING_EXIT%"=="0" (echo TES LULUS.) else (echo TES GAGAL. Salin pesan di atas untuk diperiksa.)
pause
exit /b %BILLING_EXIT%
