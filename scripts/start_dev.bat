@echo off
chcp 65001 >nul
set "ROOT=%~dp0.."
cd /d "%ROOT%"

echo 패션 크롤링 개발 서버 시작...
echo.

start "Fashion Crawling API" cmd /k "cd /d \"%ROOT%\backend\" && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
timeout /t 2 /nobreak >nul
start "Fashion Crawling UI" cmd /k "cd /d \"%ROOT%\frontend\" && npm run dev"

echo API  : http://127.0.0.1:8000
echo UI   : http://localhost:5173
echo Docs : http://127.0.0.1:8000/docs
echo.
echo 두 개의 터미널 창이 열립니다. 종료하려면 각 창에서 Ctrl+C 를 누르세요.
