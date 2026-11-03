@echo off
cd /d "%~dp0"
python -m decision_floor run --input sample_inputs\missed --config config\sources.json --workspace local_state --out local_report
if errorlevel 1 exit /b 1
start "" "%~dp0local_report\index.html"
