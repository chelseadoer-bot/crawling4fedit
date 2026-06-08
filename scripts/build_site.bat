@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo 패션 크롤링 사이트 — 정적 HTML 빌드
cd frontend
call npm run build
if errorlevel 1 exit /b 1
cd ..
if exist site rmdir /s /q site
mkdir site
xcopy /e /i /y frontend\dist\* site\
echo.
echo 완료: site\ 폴더에 HTML이 생성되었습니다.
echo 공유: site 폴더를 zip으로 보내거나, build_and_serve.bat 로 서버 실행
