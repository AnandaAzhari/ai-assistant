@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if errorlevel 1 goto use_python
py -3 main.py
goto done
:use_python
where python >nul 2>&1
if errorlevel 1 goto missing
python main.py
goto done
:missing
echo Python belum ditemukan. Baca docs/PANDUAN_WINDOWS.md untuk pemasangan.
:done
pause
