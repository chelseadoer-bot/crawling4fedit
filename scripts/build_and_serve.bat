@echo off
chcp 65001 >nul
cd /d "%~dp0.."
call scripts\build_site.bat
if errorlevel 1 exit /b 1
echo.
echo 백엔드+사이트 서버 시작 (http://127.0.0.1:8000)
echo 같은 Wi-Fi에서 공유: http://내IP:8000
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
