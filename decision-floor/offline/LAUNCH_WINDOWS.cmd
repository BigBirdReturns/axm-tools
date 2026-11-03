@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 app.py serve --project local_customer
) else (
  python app.py serve --project local_customer
)
pause
