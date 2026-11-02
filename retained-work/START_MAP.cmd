@echo off
cd /d "%~dp0"
py -3 -B scripts/serve_local.py
if errorlevel 1 pause
