@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set "PYTHON=py -3") else (set "PYTHON=python")
%PYTHON% tools\seed_demo.py --project local_demo --scenario missed
if errorlevel 1 pause & exit /b 1
%PYTHON% app.py serve --project local_demo
pause
