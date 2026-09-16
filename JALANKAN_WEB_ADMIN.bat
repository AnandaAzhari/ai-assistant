@echo off
cd /d "%~dp0"
echo Menjalankan Taqi AI Web Admin...
py -3 -c "from app.env import load_env; load_env('.env'); from app.web_admin import create_server, env_admin_key; s=create_server('127.0.0.1',8081,admin_key=env_admin_key()); print('Buka http://localhost:8081'); s.serve_forever()"
pause
