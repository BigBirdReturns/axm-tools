@echo off
setlocal
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 "%~dp0scripts\launch.py" %*
) else (
  python "%~dp0scripts\launch.py" %*
)
if errorlevel 1 pause
