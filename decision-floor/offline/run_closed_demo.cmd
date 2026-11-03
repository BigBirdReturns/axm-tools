@echo off
cd /d "%~dp0"
python -m decision_floor run --input sample_inputs\closed --config config\sources.json --workspace closed_state --out closed_report
if errorlevel 1 exit /b 1
start "" "%~dp0closed_report\index.html"
