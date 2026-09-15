@echo off
cd /d "%~dp0"
echo Menjalankan Taqi AI Web Admin...
py -3 -c "from app.web_admin import create_server; s=create_server('127.0.0.1',8081); print('Buka http://localhost:8081'); s.serve_forever()"
pause
