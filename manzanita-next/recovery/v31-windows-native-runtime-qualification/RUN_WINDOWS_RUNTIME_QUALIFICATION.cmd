@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
set "RECEIPT=%~1"
if not defined RECEIPT set "RECEIPT=%TEMP%\V31_WINDOWS_NATIVE_RUNTIME_QUALIFICATION_RECEIPT.json"
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0run_windows_runtime_qualification.ps1" -ReceiptPath "%RECEIPT%"
exit /b %ERRORLEVEL%
